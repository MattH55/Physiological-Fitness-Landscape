"""
FTP Deployment Script for Physiological Fitness Landscape.
Uploads the standalone dashboard build or frontend directory to an FTP server.

Usage:
  python deploy_ftp.py --host <FTP_HOST> --user <USER> --password <PASS> --remote-dir <REMOTE_PATH>
  Or configure environment variables: FTP_HOST, FTP_USER, FTP_PASS, FTP_DIR, FTP_PORT (optional)
"""

import os
import sys
import argparse
import ftplib
from pathlib import Path


def upload_file_ftp(ftp: ftplib.FTP, local_path: Path, remote_filename: str):
    print(f"Uploading {local_path.name} -> {remote_filename} ({local_path.stat().st_size / 1024:.1f} KB)...")
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {remote_filename}", f)
    print(f"Successfully uploaded {remote_filename}")


def deploy():
    parser = argparse.ArgumentParser(description="Deploy dashboard via FTP")
    parser.add_argument("--host", default=os.getenv("FTP_HOST"), help="FTP host / server")
    parser.add_argument("--port", type=int, default=int(os.getenv("FTP_PORT", 21)), help="FTP port (default: 21)")
    parser.add_argument("--user", default=os.getenv("FTP_USER"), help="FTP username")
    parser.add_argument("--password", default=os.getenv("FTP_PASS"), help="FTP password")
    parser.add_argument("--remote-dir", default=os.getenv("FTP_DIR", "/public_html"), help="Remote target directory")
    parser.add_argument("--file", default="dist/index.html", help="File to deploy (default: dist/index.html)")
    parser.add_argument("--tls", action="store_true", help="Use FTPS (FTP over TLS)")

    args = parser.parse_args()

    if not args.host or not args.user or not args.password:
        print("Error: Missing FTP credentials.")
        print("Please provide --host, --user, and --password as arguments or via environment variables (FTP_HOST, FTP_USER, FTP_PASS).")
        sys.exit(1)

    local_file = Path(args.file)
    if not local_file.exists():
        # Fallback check
        if Path("index.html").exists():
            local_file = Path("index.html")
        elif Path("frontend/index.html").exists():
            local_file = Path("frontend/index.html")
        else:
            print(f"Error: Target file '{args.file}' not found.")
            sys.exit(1)

    print(f"Connecting to FTP server {args.host}:{args.port} as '{args.user}'...")
    try:
        if args.tls:
            ftp = ftplib.FTP_TLS()
            ftp.connect(args.host, args.port, timeout=30)
            ftp.login(args.user, args.password)
            ftp.prot_p()
        else:
            ftp = ftplib.FTP()
            ftp.connect(args.host, args.port, timeout=30)
            ftp.login(args.user, args.password)

        print(f"Logged in successfully. Changing directory to '{args.remote_dir}'...")
        try:
            ftp.cwd(args.remote_dir)
        except ftplib.error_perm:
            print(f"Remote directory '{args.remote_dir}' does not exist or cannot be accessed directly. Trying to create or stay in root...")

        upload_file_ftp(ftp, local_file, "index.html")
        ftp.quit()
        print("\n=== Deployment completed successfully! ===")
    except Exception as e:
        print(f"\nDeployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    deploy()
