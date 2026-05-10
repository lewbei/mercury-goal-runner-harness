"""
Harness-native cryptographic artifact signing.

Inspired by VET (Oxford, Dec 2025) for host-independent agent authentication.
Uses Ed25519 public-key signatures to prove agent artifacts weren't tampered
with after generation.

Protocol:
    1. Agent generates or loads an Ed25519 keypair
    2. Agent signs each output artifact (hash of file content)
    3. Signature stored in <artifact>.sig alongside artifact
    4. Certifier verifies all signatures in the chain before accepting artifacts

Usage:
    python harness_signing.py keygen <run_dir>     — generate agent keypair
    python harness_signing.py sign <run_dir> <file> — sign an artifact
    python harness_signing.py verify <run_dir>      — verify all signatures
"""

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = "agent_key.json"  # private (kept by agent)
PUB_KEY_FILE = "agent_pubkey.json"  # public (shared with certifier)
SIG_EXT = ".sig"


class HarnessSigner:
    """Ed25519 signer for artifact authentication."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.key_path = self.run_dir / KEY_FILE
        self.pub_path = self.run_dir / PUB_KEY_FILE
        self._private_key = None

    def generate_keypair(self) -> dict:
        """Generate a new Ed25519 keypair."""
        if not HAS_CRYPTO:
            return self._fallback_keypair()

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Serialize private key
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Serialize public key
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        key_data = {
            "algorithm": "Ed25519",
            "private_key_b64": base64.b64encode(private_bytes).decode("utf-8"),
            "public_key_b64": base64.b64encode(public_bytes).decode("utf-8"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "harness_signing"
        }

        pub_data = {
            "algorithm": "Ed25519",
            "public_key_b64": base64.b64encode(public_bytes).decode("utf-8"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "harness_signing"
        }

        self.key_path.write_text(json.dumps(key_data, indent=2))
        self.pub_path.write_text(json.dumps(pub_data, indent=2))

        self._private_key = private_key
        return key_data

    def _fallback_keypair(self) -> dict:
        """Generate a fallback HMAC-based keypair when cryptography lib unavailable."""
        random_bytes = os.urandom(32)
        salt = os.urandom(16)

        key_data = {
            "algorithm": "HMAC-SHA256-FALLBACK",
            "secret_key_b64": base64.b64encode(random_bytes).decode("utf-8"),
            "salt_b64": base64.b64encode(salt).decode("utf-8"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "harness_signing",
            "note": "cryptography library not installed — using HMAC fallback"
        }

        pub_data = {
            "algorithm": "HMAC-SHA256-FALLBACK",
            "verification_key_b64": base64.b64encode(salt).decode("utf-8"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "harness_signing",
            "note": "cryptography library not installed — using HMAC fallback"
        }

        self.key_path.write_text(json.dumps(key_data, indent=2))
        self.pub_path.write_text(json.dumps(pub_data, indent=2))
        return key_data

    def load_key(self) -> bool:
        """Load existing keypair from run_dir."""
        if not self.key_path.exists():
            return False

        key_data = json.loads(self.key_path.read_text(encoding="utf-8"))

        if key_data.get("algorithm") == "Ed25519" and HAS_CRYPTO:
            private_bytes = base64.b64decode(key_data["private_key_b64"])
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
            return True
        elif key_data.get("algorithm") == "HMAC-SHA256-FALLBACK":
            return True  # Fallback signer uses key_data directly

        return False

    def sign_file(self, filepath: Path) -> dict:
        """Sign a file and write .sig file."""
        if not filepath.exists():
            return {"error": f"File not found: {filepath}"}

        content = filepath.read_bytes()
        content_hash = hashlib.sha256(content).digest()

        if self._private_key and HAS_CRYPTO:
            signature = self._private_key.sign(content_hash)
            sig_b64 = base64.b64encode(signature).decode("utf-8")
            algorithm = "Ed25519"
        else:
            # Fallback HMAC
            key_data = json.loads(self.key_path.read_text(encoding="utf-8"))
            secret = base64.b64decode(key_data["secret_key_b64"])
            salt = base64.b64decode(key_data["salt_b64"])
            hmac = self._hmac_sha256(secret, content_hash, salt)
            sig_b64 = base64.b64encode(hmac).decode("utf-8")
            algorithm = "HMAC-SHA256"

        sig_data = {
            "artifact": str(filepath.relative_to(self.run_dir)),
            "artifact_hash_sha256": base64.b64encode(content_hash).decode("utf-8"),
            "signature_b64": sig_b64,
            "algorithm": algorithm,
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signed_by_key_id": self._key_id()
        }

        sig_path = filepath.with_suffix(filepath.suffix + SIG_EXT)
        sig_path.write_text(json.dumps(sig_data, indent=2))

        return sig_data

    def verify_file(self, filepath: Path) -> dict:
        """Verify a file's signature."""
        sig_path = filepath.with_suffix(filepath.suffix + SIG_EXT)

        if not filepath.exists():
            return {"verdict": "INDETERMINATE", "reason": f"File not found: {filepath}"}

        if not sig_path.exists():
            return {
                "verdict": "UNSIGNED",
                "reason": f"No signature file found",
                "artifact": str(filepath.relative_to(self.run_dir))
            }

        sig_data = json.loads(sig_path.read_text(encoding="utf-8"))
        content = filepath.read_bytes()
        content_hash = hashlib.sha256(content).digest()

        declared_hash = base64.b64decode(sig_data["artifact_hash_sha256"])

        if content_hash != declared_hash:
            return {
                "verdict": "TAMPERED",
                "reason": "Content hash mismatch — file was modified after signing",
                "artifact": str(filepath.relative_to(self.run_dir))
            }

        if sig_data["algorithm"] == "Ed25519" and HAS_CRYPTO:
            try:
                pub_data = json.loads(self.pub_path.read_text(encoding="utf-8"))
                public_bytes = base64.b64decode(pub_data["public_key_b64"])
                public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
                signature = base64.b64decode(sig_data["signature_b64"])
                public_key.verify(signature, content_hash)
                return {
                    "verdict": "AUTHENTIC",
                    "reason": "Ed25519 signature verified",
                    "artifact": str(filepath.relative_to(self.run_dir))
                }
            except InvalidSignature:
                return {
                    "verdict": "FORGED",
                    "reason": "Ed25519 signature invalid — key mismatch or tampering",
                    "artifact": str(filepath.relative_to(self.run_dir))
                }
            except Exception as e:
                return {
                    "verdict": "INDETERMINATE",
                    "reason": f"Verification error: {e}",
                    "artifact": str(filepath.relative_to(self.run_dir))
                }
        elif sig_data["algorithm"] == "HMAC-SHA256":
            # Verify fallback HMAC
            key_data = json.loads(self.key_path.read_text(encoding="utf-8"))
            secret = base64.b64decode(key_data["secret_key_b64"])
            salt = base64.b64decode(key_data["salt_b64"])
            expected = self._hmac_sha256(secret, content_hash, salt)
            actual = base64.b64decode(sig_data["signature_b64"])
            if hashlib.sha256(expected).digest() == hashlib.sha256(actual).digest():
                return {
                    "verdict": "AUTHENTIC",
                    "reason": "HMAC verified (fallback)",
                    "artifact": str(filepath.relative_to(self.run_dir))
                }
            else:
                return {
                    "verdict": "FORGED",
                    "reason": "HMAC mismatch",
                    "artifact": str(filepath.relative_to(self.run_dir))
                }

        return {
            "verdict": "UNKNOWN",
            "reason": f"Unknown algorithm: {sig_data['algorithm']}",
            "artifact": str(filepath.relative_to(self.run_dir))
        }

    def verify_all(self) -> list[dict]:
        """Verify all signed artifacts in the run directory."""
        results = []
        for sig_path in self.run_dir.rglob(f"*{SIG_EXT}"):
            artifact_name = sig_path.name[:-len(SIG_EXT)]
            artifact_dir = sig_path.parent
            artifact_path = artifact_dir / artifact_name
            if artifact_path.exists():
                results.append(self.verify_file(artifact_path))
        return results

    def _key_id(self) -> str:
        """Generate a key identifier from the public key."""
        if self.pub_path.exists():
            pub = json.loads(self.pub_path.read_text(encoding="utf-8"))
            return hashlib.sha256(pub["public_key_b64"].encode()).hexdigest()[:16]
        return "unknown"

    @staticmethod
    def _hmac_sha256(key: bytes, data: bytes, salt: bytes) -> bytes:
        """HMAC-SHA256 fallback."""
        import hmac
        return hmac.new(key, data + salt, hashlib.sha256).digest()


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python harness_signing.py keygen <run_dir>")
        print("  python harness_signing.py sign <run_dir> <file>")
        print("  python harness_signing.py verify <run_dir>")
        sys.exit(1)

    cmd = sys.argv[1]
    run_dir = Path(sys.argv[2])

    if not run_dir.exists():
        print(f"Error: run directory not found: {run_dir}")
        sys.exit(1)

    signer = HarnessSigner(run_dir)

    if cmd == "keygen":
        if signer.load_key():
            print("Key already exists")
        else:
            signer.generate_keypair()
            print("Keypair generated")

    elif cmd == "sign":
        if not signer.load_key():
            signer.generate_keypair()
            print("Generated new keypair first")

        filepath = Path(sys.argv[3]) if len(sys.argv) > 3 else None
        if not filepath:
            # Sign all .py artifacts
            for py_file in run_dir.rglob("*.py"):
                sig = signer.sign_file(py_file)
                print(f"Signed: {py_file.name}")
        else:
            sig = signer.sign_file(Path(filepath))
            print(json.dumps(sig, indent=2))

    elif cmd == "verify":
        if not signer.pub_path.exists():
            # Generate key for fresh verification
            if not signer.load_key():
                signer.generate_keypair()

        results = signer.verify_all()
        if not results:
            print("No signed artifacts found")
        else:
            for r in results:
                status = "PASS" if r["verdict"] == "AUTHENTIC" else "FAIL"
                print(f"{status} {r['artifact']}: {r['verdict']} — {r['reason']}")

            verdicts = [r["verdict"] for r in results]
            if all(v == "AUTHENTIC" for v in verdicts):
                print("\nALL ARTIFACTS AUTHENTIC — no tampering detected")
            elif any(v in ("FORGED", "TAMPERED") for v in verdicts):
                print("\nWARNING: TAMPERING DETECTED - some artifacts compromised")
            else:
                print(f"\nMixed results: {len(verdicts)} artifacts checked")


if __name__ == "__main__":
    main()
