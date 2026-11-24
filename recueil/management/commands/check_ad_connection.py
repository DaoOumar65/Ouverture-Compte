import ssl

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check LDAP transport, service bind, and base-DN search for the configured AD connection."

    def handle(self, *args, **options):
        if settings.AUTH_MODE != "AD":
            raise CommandError("AUTH_MODE is not AD.")
        if not all((settings.AD_HOST, settings.AD_BIND_DN, settings.AD_BIND_PASSWORD, settings.AD_BASE_DN)):
            raise CommandError("AD connection settings are incomplete; secret values were not displayed.")

        try:
            from ldap3 import Connection, Server, Tls, SUBTREE
            from ldap3.core.exceptions import LDAPException
        except ImportError as exc:
            raise CommandError("Install project dependencies before checking AD.") from exc

        timeout = max(1, settings.AD_TIMEOUT_MS) / 1000
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_file=settings.AD_CA_CERT or None,
        )
        server = Server(
            settings.AD_HOST,
            port=settings.AD_PORT,
            use_ssl=settings.AD_TLS == "ldaps",
            tls=tls,
            connect_timeout=timeout,
        )
        connection = Connection(
            server,
            user=settings.AD_BIND_DN,
            password=settings.AD_BIND_PASSWORD,
            receive_timeout=timeout,
            auto_bind=False,
        )

        stage = "LDAP socket"
        try:
            # ldap3's synchronous Connection.open() returns None on success;
            # socket failures raise LDAPSocketOpenError instead.
            connection.open(read_server_info=False)
            if settings.AD_TLS == "none":
                self.stdout.write(self.style.SUCCESS("LDAP socket (no TLS): OK"))
            elif settings.AD_TLS == "ldaps":
                self.stdout.write(self.style.SUCCESS("LDAPS handshake: OK"))

            if settings.AD_TLS == "starttls":
                stage = "StartTLS"
                if not connection.start_tls():
                    self._report_ldap_failure(stage, connection)
                    raise CommandError("AD connection check failed.")
                self.stdout.write(self.style.SUCCESS("StartTLS: OK"))

            stage = "service-account bind"
            if not connection.bind():
                self._report_ldap_failure(stage, connection)
                raise CommandError("AD connection check failed.")
            self.stdout.write(self.style.SUCCESS("Read-only service bind: OK"))

            stage = "base-DN search"
            if not connection.search(
                settings.AD_BASE_DN,
                "(objectClass=*)",
                search_scope=SUBTREE,
                attributes=["objectClass"],
                size_limit=1,
            ):
                self._report_ldap_failure(stage, connection)
                raise CommandError("AD connection check failed.")
            self.stdout.write(self.style.SUCCESS("Base-DN search: OK"))
        except (LDAPException, OSError, ValueError) as exc:
            hint = self._safe_error_hint(exc, connection)
            self.stderr.write(self.style.ERROR(
                f"{stage} failed (mode={settings.AD_TLS}; port={settings.AD_PORT}; "
                f"{type(exc).__name__}; {hint}). No credentials were printed."
            ))
            raise CommandError("AD connection check failed.") from None
        finally:
            try:
                connection.unbind()
            except Exception:
                pass

    def _report_ldap_failure(self, stage, connection):
        result = connection.result or {}
        hint = self._safe_error_hint(None, connection)
        self.stderr.write(self.style.ERROR(
            f"{stage} failed (LDAP result={result.get('result', 'unavailable')}; "
            f"description={result.get('description', 'unavailable')}; hint={hint})."
        ))

    @staticmethod
    def _safe_error_hint(exc, connection=None):
        messages = [str(arg) for arg in getattr(exc, "args", ())] if exc else []
        if connection is not None and connection.last_error:
            messages.append(str(connection.last_error))
        message = " ".join(messages).casefold()
        hints = (
            (("timed out",), "socket timeout"),
            (("connection refused", "actively refused"), "connection refused"),
            (("getaddrinfo failed", "name or service not known", "name resolution"), "DNS resolution failed"),
            (("certificate verify failed", "certificateverifyfailed", "unknown ca", "bad certificate"), "TLS certificate validation failed"),
            (("wrong version number", "unknown protocol", "protocol version"), "TLS protocol mismatch"),
            (("handshake failure", "handshake failed", "sslv3 alert", "tlsv1 alert"), "TLS handshake rejected by the server"),
            (("unexpected eof", "connection reset", "peer closed", "server disconnected"), "server closed the TLS/socket connection"),
            (("ssl wrapping error", "ssl error"), "TLS negotiation failed"),
            (("no route to host", "network is unreachable"), "network route unavailable"),
        )
        for needles, hint in hints:
            if any(needle in message for needle in needles):
                return hint
        return "check host, port, and TLS configuration"
