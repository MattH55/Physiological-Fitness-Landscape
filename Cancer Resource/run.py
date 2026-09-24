"""Dev server entry point: python run.py"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("synlethality.main:app", host="127.0.0.1", port=8100, reload=True)
