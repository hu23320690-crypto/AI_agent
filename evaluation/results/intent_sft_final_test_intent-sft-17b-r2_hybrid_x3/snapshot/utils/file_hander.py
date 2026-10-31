import hashlib
from pathlib import Path
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

def get_file_md5_hex(filepath: str) -> str:
    with open(filepath, "rb") as file:
        return hashlib.file_digest(file, "md5").hexdigest()

def listdir_with_allowed_type(path: str, allowed_types: tuple[str]) -> tuple[str, ...]:
    folder = Path(path)
    if not folder.is_dir():
        raise FileNotFoundError(f"知识库目录不存在：{path}")
    suffixes = {"." + item.lower().lstrip(".") for item in allowed_types}
    return tuple(str(p) for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in suffixes)

def pdf_loader(filepath: str, passwd=None) -> list[Document]:
    return PyPDFLoader(filepath, password=passwd).load()

def txt_loader(filepath: str) -> list[Document]:
    return TextLoader(filepath, encoding="utf-8-sig").load()
