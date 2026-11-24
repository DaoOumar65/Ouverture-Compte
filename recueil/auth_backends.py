"""Authentication backend for the BCB Active Directory."""
import logging
import ssl

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db import transaction

logger = logging.getLogger(__name__)


class ActiveDirectoryBackend(ModelBackend):
    """Validate credentials against AD, then keep a local Django identity/profile."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        username = (username or kwargs.get("user") or "").strip()
        if not username or not password:
            return None

        try:
            from ldap3 import Connection, Server, Tls
            from ldap3.core.exceptions import LDAPException
            from ldap3.utils.conv import escape_filter_chars
        except ImportError:
            logger.error("AD login unavailable: install the ldap3 dependency.")
            return None

        host = getattr(settings, "AD_HOST", "")
        bind_dn = getattr(settings, "AD_BIND_DN", "")
        bind_password = getattr(settings, "AD_BIND_PASSWORD", "")
        base_dn = getattr(settings, "AD_BASE_DN", "")
        tls_mode = getattr(settings, "AD_TLS", "ldaps").lower()
        timeout = max(1, getattr(settings, "AD_TIMEOUT_MS", 5000)) / 1000
        if not all((host, bind_dn, bind_password, base_dn)):
            logger.error("AD login unavailable: directory connection settings are incomplete.")
            return None

        account = self._account_name(username)
        if not account:
            return None

        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_file=getattr(settings, "AD_CA_CERT", "") or None,
        )
        server = Server(
            host,
            port=settings.AD_PORT,
            use_ssl=tls_mode == "ldaps",
            tls=tls,
            connect_timeout=timeout,
        )

        service = user_connection = None
        stage = "service-account connection"
        try:
            service = self._open_connection(
                Connection(
                    server,
                    user=bind_dn,
                    password=bind_password,
                    receive_timeout=timeout,
                    auto_bind=False,
                ),
                tls_mode,
                "service-account bind",
            )
            if not service:
                return None
            stage = "directory user search"
            if not service.search(
                base_dn,
                "(&(objectCategory=person)(objectClass=user)"
                "(sAMAccountName={})(!(userAccountControl:1.2.840.113556.1.4.803:=2)))".format(
                    escape_filter_chars(account)
                ),
                attributes=["sAMAccountName", "givenName", "sn", "mail", "displayName"],
                size_limit=2,
            ):
                self._log_ldap_result(stage, service)
                return None

            entries = [item for item in service.entries if item.entry_dn]
            if len(entries) != 1:
                return None

            entry = entries[0]
            stage = "user credential bind"
            user_connection = self._open_connection(
                Connection(
                    server,
                    user=entry.entry_dn,
                    password=password,
                    receive_timeout=timeout,
                    auto_bind=False,
                ),
                tls_mode,
                "user credential bind",
            )
            if not user_connection:
                return None

            attributes = entry.entry_attributes_as_dict
            sam_account = self._attribute(attributes, "sAMAccountName") or account
            return self._get_or_update_user(sam_account, attributes)
        except (LDAPException, OSError, ValueError) as exc:
            # Never log the submitted password or the service-account credentials.
            cause = exc.__cause__ or exc.__context__
            cause_type = type(cause).__name__ if cause else "none"
            cause_errno = getattr(cause, "errno", None) if cause else None
            tls_verify_code = getattr(exc, "verify_code", None)
            safe_hint = self._safe_error_hint(exc)
            logger.warning(
                "AD authentication failed during %s (%s; cause=%s; errno=%s; tls_verify_code=%s; hint=%s).",
                stage,
                type(exc).__name__,
                cause_type,
                cause_errno,
                tls_verify_code,
                safe_hint,
            )
            return None
        finally:
            for connection in (user_connection, service):
                if connection is not None:
                    try:
                        connection.unbind()
                    except Exception:  # LDAP cleanup must not leak credentials or mask the result.
                        pass

    @staticmethod
    def _account_name(login):
        netbios = getattr(settings, "AD_DOMAIN_NETBIOS", "").casefold()
        suffixes = {
            item.strip().casefold()
            for item in getattr(settings, "AD_UPN_SUFFIXES", ())
            if item.strip()
        }
        if "\\" in login:
            domain, account = login.split("\\", 1)
            if not netbios or domain.casefold() != netbios:
                return None
            return account.strip() or None
        if "@" in login:
            account, suffix = login.rsplit("@", 1)
            if suffix.casefold() not in suffixes:
                return None
            return account.strip() or None
        return login or None

    @staticmethod
    def _open_connection(connection, tls_mode, stage):
        # ldap3's synchronous Connection.open() returns None on success; failures
        # are raised as LDAPSocketOpenError. Do not treat its return value as a bool.
        # Skip anonymous RootDSE/schema discovery before the authenticated bind.
        connection.open(read_server_info=False)
        if tls_mode == "starttls" and not connection.start_tls():
            ActiveDirectoryBackend._log_ldap_result(f"{stage}: StartTLS", connection)
            connection.unbind()
            return None
        if tls_mode not in {"ldaps", "starttls", "none"} or not connection.bind():
            ActiveDirectoryBackend._log_ldap_result(stage, connection)
            connection.unbind()
            return None
        return connection

    @staticmethod
    def _log_ldap_result(stage, connection):
        result = getattr(connection, "result", None) or {}
        logger.warning(
            "AD %s failed (LDAP result=%s, description=%s).",
            stage,
            result.get("result", "unavailable"),
            result.get("description", "unavailable"),
        )

    @staticmethod
    def _safe_error_hint(exc):
        # Map exception text to fixed labels; never include arbitrary LDAP/socket text in logs.
        message = " ".join(str(arg) for arg in getattr(exc, "args", ())).casefold()
        hints = (
            (("timed out", "timeout"), "socket timeout"),
            (("connection refused", "actively refused"), "connection refused"),
            (("getaddrinfo failed", "name or service not known", "name resolution"), "DNS resolution failed"),
            (("certificate verify failed", "certificateverifyfailed"), "TLS certificate validation failed"),
            (("wrong version number", "unknown protocol"), "TLS protocol mismatch"),
            (("no route to host", "network is unreachable"), "network route unavailable"),
        )
        for needles, hint in hints:
            if any(needle in message for needle in needles):
                return hint
        return "no safe low-level hint available"

    @staticmethod
    def _attribute(attributes, name):
        values = attributes.get(name, [])
        return str(values[0]).strip() if values else ""

    @transaction.atomic
    def _get_or_update_user(self, account, attributes):
        User = get_user_model()
        username = account.casefold()
        first_name = self._attribute(attributes, "givenName")
        last_name = self._attribute(attributes, "sn")
        email = self._attribute(attributes, "mail")
        display_name = self._attribute(attributes, "displayName")

        user = User.objects.filter(username__iexact=username).first()
        if user is not None and not user.is_active:
            return None
        if user is None:
            user = User(username=username, is_active=True)
            user.set_unusable_password()

        user.first_name = first_name[:150]
        user.last_name = last_name[:150]
        user.email = email[:254]
        if not user.pk or user.has_usable_password():
            user.set_unusable_password()
        user.save()

        profile = user.profile
        if display_name and not profile.nom_affiche:
            profile.nom_affiche = display_name[:150]
            profile.save(update_fields=["nom_affiche"])
        return user
