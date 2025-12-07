from abc import ABC, abstractmethod
from typing import List


class Embedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return embedding for each input text."""
        raise NotImplementedError

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]
