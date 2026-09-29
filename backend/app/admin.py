"""Local administrative CLI for enrollment, revocation, and isolated demonstration credentials."""
import argparse
import asyncio
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.database import Database
from backend.app.security import PASSWORDS, hash_token
from backend.app.tables import Audit, Credential, Organization, User
from common.contracts import utcnow


async def seed_demo(output: Path) -> None:
    """Create distinct identities and store credentials locally, never in repository history."""
    if output.exists():
        raise RuntimeError("credential_output_already_exists")
    db = Database(get_settings())
    credentials = {"schema_version": 1, "organizations": []}
    try:
        async with db.sessions() as session, session.begin():
            if await session.scalar(select(User.id).limit(1)):
                raise RuntimeError("database_already_enrolled")
            password = secrets.token_urlsafe(20)
            session.add(User(email="admin@threatscope.local", password_hash=PASSWORDS.hash(password), role="admin"))
            credentials["admin"] = {"email": "admin@threatscope.local", "password": password}
            for name in ("Orion", "Lyra", "Vega"):
                org = Organization(name=name, provenance_group=name.lower())
                session.add(org)
                await session.flush()
                key, org_password = secrets.token_urlsafe(32), secrets.token_urlsafe(20)
                credential = Credential(
                    org_id=org.id, key_hash=hash_token(key), expires_at=utcnow() + timedelta(days=90),
                )
                session.add(credential)
                email = name.lower() + "@threatscope.local"
                session.add(User(
                    email=email, password_hash=PASSWORDS.hash(org_password), role="analyst", org_id=org.id,
                ))
                await session.flush()
                credentials["organizations"].append({
                    "name": name, "org_id": org.id, "api_key": key, "credential_id": credential.id,
                    "email": email, "password": org_password,
                })
            session.add(Audit(actor_id="local_admin", action="demo_enrollment", resource_id=None))
            output.parent.mkdir(parents=True, exist_ok=True)
            # Refuse replacement. POSIX permissions restrict access; Windows uses the user's folder ACL.
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(credentials, stream, indent=2)
            for item in credentials["organizations"]:
                node_file = output.parent / (item["name"].lower() + "-node.json")
                descriptor = os.open(node_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump({k: item[k] for k in ("org_id", "api_key", "credential_id")}, stream)
    finally:
        await db.close()
    print(f"Enrollment complete. Private credentials saved to {output.resolve()}")


async def revoke(credential_id: str):
    db = Database(get_settings())
    try:
        async with db.sessions() as session, session.begin():
            credential = await session.get(Credential, credential_id)
            if credential is None:
                raise RuntimeError("credential_not_found")
            credential.active = False
            session.add(Audit(actor_id="local_admin", action="credential_revoked", resource_id=credential_id))
    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed-demo")
    seed.add_argument("--output", type=Path, default=Path(".runtime/demo-credentials.json"))
    revoke_parser = sub.add_parser("revoke")
    revoke_parser.add_argument("credential_id")
    args = parser.parse_args()
    if args.command == "seed-demo":
        asyncio.run(seed_demo(args.output))
    else:
        asyncio.run(revoke(args.credential_id))


if __name__ == "__main__":
    main()

