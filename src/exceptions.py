from fastapi import HTTPException, status

def exception(error, desc):
    raise HTTPException(
        status_code=error,
        detail=f"{desc}",
        headers={"WWW-Authenticate": "Bearer"},
    )