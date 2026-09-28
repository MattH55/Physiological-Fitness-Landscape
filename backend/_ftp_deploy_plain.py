"""FTP deployment - plain FTP (no TLS) for reliability."""
import ftplib
from pathlib import Path

HOST = "opensourcemed.info"
PORT = 21
USER = "LandscapeAccess@landscape.opensourcemed.info"
PASS = "VUlovelovelove69"
LOCAL_FILE = Path(__file__).resolve().parent.parent / "dist" / "index.html"

def main():
    ftp = ftplib.FTP()
    ftp.connect(HOST, PORT, timeout=60)
    ftp.login(USER, PASS)
    print(f"Connected. PWD: {ftp.pwd()}")
    
    # Upload to root
    size = LOCAL_FILE.stat().st_size
    print(f"Uploading {LOCAL_FILE.name} ({size / 1024:.1f} KB) to /index.html...")
    with open(LOCAL_FILE, "rb") as f:
        ftp.storbinary(f"STOR index.html", f)
    print("Upload to /index.html complete!")
    
    # Also upload to dist/
    try:
        ftp.cwd("/dist")
        print(f"Uploading to /dist/index.html...")
        with open(LOCAL_FILE, "rb") as f:
            ftp.storbinary(f"STOR index.html", f)
        print("Upload to /dist/index.html complete!")
    except Exception as e:
        print(f"Could not upload to /dist: {e}")
    
    ftp.quit()
    print("Done.")

if __name__ == "__main__":
    main()