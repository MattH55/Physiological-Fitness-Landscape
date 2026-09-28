"""FTP deployment script with directory exploration."""
import ftplib
import sys
from pathlib import Path

HOST = "opensourcemed.info"
PORT = 21
USER = "LandscapeAccess@landscape.opensourcemed.info"
PASS = "VUlovelovelove69"
LOCAL_FILE = Path(__file__).resolve().parent.parent / "dist" / "index.html"

def main():
    ftp = ftplib.FTP_TLS()
    ftp.connect(HOST, PORT, timeout=30)
    ftp.login(USER, PASS)
    ftp.prot_p()
    
    print(f"Connected. PWD: {ftp.pwd()}")
    print(f"Files in current dir: {ftp.nlst()}")
    
    # Try common paths
    for path in ["/", "/home", "/home/openwjgl", "/public_html", "/var/www", "/var/www/html"]:
        try:
            ftp.cwd(path)
            print(f"\nCD {path}: OK")
            print(f"  Contents: {ftp.nlst()}")
        except Exception as e:
            print(f"\nCD {path}: {e}")
    
    # Upload to current directory
    print(f"\nUploading {LOCAL_FILE.name} ({LOCAL_FILE.stat().st_size / 1024:.1f} KB) to current dir...")
    with open(LOCAL_FILE, "rb") as f:
        ftp.storbinary(f"STOR index.html", f)
    print("Upload complete!")
    
    ftp.quit()
    print("Done.")

if __name__ == "__main__":
    main()