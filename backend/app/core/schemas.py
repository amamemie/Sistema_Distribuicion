from pydantic import BaseModel, ConfigDict


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    pagina: int
    tamano: int
