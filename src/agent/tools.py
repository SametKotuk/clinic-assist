import json
from html import escape
from pathlib import Path
from google.genai import types
from src.booking.schedule import TREATMENTS
from src.booking.service import BookingError, BookingService

TREATMENT_LIST = "; ".join(f"{t.id} = {t.label}" for t in TREATMENTS.values())

# Belgelerin bulunduğu klasör
ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "data" / "docs"

TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="retrieve_docs",
                description="Klinik belgelerinde arama yapar. Fiyat, kurallar veya bilgi sorulduğunda çağır.",
                parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}
            ),
            types.FunctionDeclaration(
                name="check_slots",
                description="Müsait randevu saatlerini döndürür.",
                parameters={"type": "OBJECT", "properties": {"date": {"type": "STRING"}, "treatment": {"type": "STRING"}}, "required": ["date", "treatment"]}
            ),
            types.FunctionDeclaration(
                name="book_appointment",
                description="Hasta onayından sonra randevu oluşturur.",
                parameters={"type": "OBJECT", "properties": {"date": {"type": "STRING"}, "time": {"type": "STRING"}, "treatment": {"type": "STRING"}, "patient_name": {"type": "STRING"}, "phone": {"type": "STRING"}, "patient_confirmed": {"type": "BOOLEAN"}}, "required": ["date", "time", "treatment", "patient_name", "phone", "patient_confirmed"]}
            )
        ]
    )
]

def _dump(obj) -> str: return json.dumps(obj, ensure_ascii=False)

class ToolExecutor:
    def __init__(self, booking: BookingService, retriever=None, top_k: int = 4):
        self.booking = booking
        self.sources = {}
        self._keys = {}
        
        # Klasördeki tüm belgeleri bul ve doğrudan hafızaya al
        docs_text = []
        if DOCS_DIR.exists():
            for i, file_path in enumerate(DOCS_DIR.glob("**/*.md"), 1):
                docs_text.append(f"<belge no=\"{i}\" kaynak=\"{file_path.name}\">\n{file_path.read_text(encoding='utf-8')}\n</belge>")
        self._all_docs = "<belgeler>\n" + "\n\n".join(docs_text) + "\n</belgeler>" if docs_text else "Belge bulunamadı."

    def run(self, name: str, args: dict) -> tuple[str, bool]:
        try:
            if name == "retrieve_docs": return self._all_docs, False
            if name == "check_slots": return _dump(self.booking.check_slots(args["date"], args["treatment"])), False
            if name == "book_appointment": return self._book(args), False
            return _dump({"error": "unknown_tool", "message": f"Bilinmeyen araç: {name}"}), True
        except BookingError as e: return _dump({"error": e.code, "message": e.message}), True
        except Exception as e: return _dump({"error": "internal", "message": str(e)}), True

    def _book(self, args: dict) -> str:
        if args.get("patient_confirmed") is not True: raise BookingError("not_confirmed", "Onay alınmadı.")
        a = self.booking.book(args["date"], args["time"], args["treatment"], args["patient_name"], args["phone"])
        return _dump({"status": "confirmed", "appointment_id": a.id, "date": a.start.strftime("%Y-%m-%d"), "time": a.start.strftime("%H:%M")})