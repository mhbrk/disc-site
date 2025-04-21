from chainlit.utils import mount_chainlit
from fastapi import FastAPI

app = FastAPI()


@app.get("/app")
def read_main():
    return {"message": "Hello World from main app"}


mount_chainlit(app=app, target="my_cl_app.py", path="/chainlit")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=7000, reload=True)
