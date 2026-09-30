import re
import os
from dataclasses import dataclass, field
from google import genai
from google.genai import types

from src.agent.agent_prompt import build_agent_prompt
from src.agent.tools import TOOLS, ToolExecutor
from src.booking.service import BookingService, istanbul_now
from src.booking.store import AppointmentStore
from src.config import settings
from src.retrieval.models import Hit

MAX_STEPS = 6

@dataclass
class ToolCall:
    name: str
    input: dict
    result: str
    is_error: bool

@dataclass
class AgentReply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    cited: list[Hit] = field(default_factory=list)
    steps: int = 0

class ClinicAgent:
    def __init__(self, client=None, booking=None, retriever=None, now_fn=istanbul_now, model="gemini-3.5-flash-lite"):
        self.now_fn = now_fn  # Saati tutan değişken (Burası silinmişti)
        self.booking = booking or BookingService(AppointmentStore(str(settings.db_path)), self.now_fn)
        if retriever is None:
            from src.retrieval.search import search as retriever
        self.tools = ToolExecutor(self.booking, retriever, settings.top_k)
        self.model = model
        self.messages = []
        
        if "GEMINI_API_KEY" not in os.environ:
            from dotenv import load_dotenv
            load_dotenv()
            
        self.client = client or genai.Client()

    def reset(self) -> None:
        self.messages.clear()
        self.tools.sources.clear()
        self.tools._keys.clear()

    def chat(self, user_message: str) -> AgentReply:
        if not user_message.strip(): return AgentReply("Mesajınızı anlayamadım.")
        
        self.messages.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
        calls = []
        
        for step in range(1, MAX_STEPS + 1):
            resp = self.client.models.generate_content(
                model=self.model,
                contents=self.messages,
                config=types.GenerateContentConfig(
                    system_instruction=build_agent_prompt(self.now_fn()),
                    tools=TOOLS,
                    temperature=0.0
                )
            )
            
            msg_content = resp.candidates[0].content
            self.messages.append(msg_content)
            
            function_calls = [p.function_call for p in msg_content.parts if p.function_call]
            
            if not function_calls:
                text = "".join(p.text for p in msg_content.parts if p.text).strip()
                nums = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
                cited = [self.tools.sources[n] for n in nums if n in self.tools.sources]
                return AgentReply(text, calls, cited, step)
                
            tool_parts = []
            for fc in function_calls:
                args_dict = dict(fc.args) if fc.args else {}
                out, is_err = self.tools.run(fc.name, args_dict)
                calls.append(ToolCall(fc.name, args_dict, out, is_err))
                tool_parts.append(types.Part.from_function_response(name=fc.name, response={"result": out}))
            
            self.messages.append(types.Content(role="user", parts=tool_parts))

        return AgentReply("İşleminizi tamamlayamadım. Lütfen klinikle iletişime geçin.", calls, [], MAX_STEPS)