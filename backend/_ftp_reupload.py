"""Re-upload standalone HTML to FTP and verify."""
import ftplib
from pathlib import Path

HOST = "opensourcemed.info"
PORT = 21
USER = "LandscapeAccess@landscape.opensourcemed.info"
PASS = "VUlovelovelove69"
LOCAL_FILE = Path(__file__).resolve().parent.parent / "dist" / "index.html"
LOG = Path(__file__).resolve().parent / "_ftp_verify.txt"

def main():
    lines = []
    try:
        ftp = ftplib.FTP_TLS()
        ftp.connect(HOST, PORT, timeout=30)
        ftp.login(USER, PASS)
        ftp.prot_p()
        lines.append(f"Connected. PWD: {ftp.pwd()}")
        lines.append(f"Local file: {LOCAL_FILE} ({LOCAL_FILE.stat().st_size / 1024:.1f} KB)")

        # Check root
        try:
            size = ftp.size('index.html')
            lines.append(f"Root index.html size: {size / 1024:.1f} KB")
        except Exception as e:
            lines.append(f"Root index.html: {e}")

        # Check dist/
        try:
            ftp.cwd('/dist')
            size = ftp.size('index.html')
            lines.append(f"dist/index.html size: {size / 1024:.1f} KB")
        except Exception as e:
            lines.append(f"dist/index.html: {e}")

        # Re-upload to root
        ftp.cwd('/')
        lines.append("Uploading to /...")
        with open(LOCAL_FILE, 'rb') as f:
            ftp.storbinary('STOR index.html', f)
        lines.append("Upload to / complete!")

        # Verify
        try:
            size = ftp.size('index.html')
            lines.append(f"Verified root index.html size: {size / 1024:.1f} KB")
        except Exception as e:
            lines.append(f"Verify failed: {e}")

        ftp.quit()
        lines.append("Done.")
    except Exception as e:
        lines.append(f"ERROR: {e}")

    LOG.write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__ == "__main__":
    main()