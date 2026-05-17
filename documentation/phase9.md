# Phase 9 — AI Fleet Expansion & SaaS Architecture (BYOK)

> **Goal:** Expand your AI trading fleet to 6+ models (Google, Groq, OpenAI, Claude, DeepSeek, Local Ollama), and build the core database & security architecture for a Bring Your Own Key (BYOK) multi-tenant SaaS.

---

## 9.1 The New 6-Agent AI Fleet

By expanding our fleet, we compare diverse cognitive styles and balance API cost constraints:

| Agent Name | Model Used | Provider | Cost Mode | Cognitive Style |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini-Flash** | `gemini-2.0-flash` | Google | Cloud API (BYOK) | Multi-modal context processing |
| **Groq-Llama** | `llama-3.3-70b` | Groq | Cloud API (BYOK) | Speed-optimized, highly rule-compliant |
| **OpenAI-Mini** | `gpt-4o-mini` | OpenAI | Cloud API (BYOK) | Exceptional JSON formatting & safety bounds |
| **Claude-Sonnet** | `claude-3-5-sonnet` | Anthropic | Cloud API (BYOK) | Deep analytical reasoning, risk-averse |
| **DeepSeek-R1** | `deepseek-reasoning` | DeepSeek | Cloud API (BYOK) | Long-chain reasoning (`<think>` blocks) |
| **Local-Ollama** | `llama-3.2-3b` | Local Ollama | **$0.00 (Free)** | Fully private, offline MacBook benchmark |

---

## 9.2 SaaS BYOK & Authentication Database Architecture

To scale from a local workspace into a SaaS, TradeOS utilizes a **Bring Your Own Key (BYOK)** design. Users securely register and upload their own API keys, paying only for their exact model usage.

```
                          ┌───────────────────────┐
                          │   JWT Authentication  │
                          └───────────┬───────────┘
                                      │
                       ┌──────────────▼──────────────┐
                       │    User Table (PostgreSQL)  │
                       │    - id, email, hashed_pwd  │
                       │    - Encrypted API Keys     │
                       └──────────────┬──────────────┘
                                      │
                      ┌───────────────▼───────────────┐
                      │    Decentralized Execution    │
                      │    - Decrypts keys at runtime │
                      │    - Queries AI using user's  │
                      │      own personal API balance │
                      └───────────────────────────────┘
```

### Database Model (`database/models.py` SaaS Extension)
```python
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database.connection import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Encrypted BYOK fields
    gemini_api_key = Column(String, nullable=True)
    groq_api_key = Column(String, nullable=True)
    openai_api_key = Column(String, nullable=True)
    anthropic_api_key = Column(String, nullable=True)
    deepseek_api_key = Column(String, nullable=True)
    
    # User-scoped portfolios
    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
```

---

## 9.3 Custom Agent Clients & SaaS Routing

### 1. DeepSeek R1 Reasoning (`agents/deepseek_agent.py`)
Queries DeepSeek-R1 and extracts the thinking trace:
```python
from openai import OpenAI
import json

async def query_deepseek(payload: dict, custom_key: str) -> dict:
    client = OpenAI(api_key=custom_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-reasoning",
        messages=[{"role": "user", "content": str(payload)}]
    )
    
    # Capture reasoning content for visual rendering in the UI!
    reasoning_trace = getattr(response.choices[0].message, "reasoning_content", "")
    parsed_json = json.loads(response.choices[0].message.content)
    
    return {
        **parsed_json,
        "reasoning_steps": reasoning_trace
    }
```

### 2. Concurrency Router inside `agent_executor.py`
The executor automatically injects the user's decrypted keys before executing parallel queries:
```python
# Inside execute_all_agents
tasks = []
for agent in agents:
    # 1. Fetch user-provided key based on provider
    api_key = decrypt_key(user.get_key_for_provider(agent.provider))
    payload = build_ai_payload(market_context, opportunity, news, agent_states[agent.name])
    
    # 2. Append asynchronous task
    if agent.provider == "google":
        tasks.append(query_gemini(payload, api_key))
    elif agent.provider == "openai":
        tasks.append(query_openai(payload, api_key))
    elif agent.provider == "deepseek":
        tasks.append(query_deepseek(payload, api_key))
    elif agent.provider == "ollama":
        tasks.append(query_ollama(payload))  # Local, no key needed!
```

---

## 9.4 UI Dashboard & Security Upgrades

*   **Secure Keys Portal**: A settings panel in the frontend where users can add, delete, or update their API keys (transmitted over HTTPS and encrypted at rest using AES-256).
*   **DeepSeek Think Panel**: A slide-down Accordion block on the stock inspection cards that displays the `<think>` steps from DeepSeek-R1, letting users see the model's math before placing the virtual trade.
*   **Model Accent Coloring**:
    *   OpenAI: Glassmorphism Emerald Green (`#10a37f`)
    *   Claude: Terracotta clay (`#d97706`)
    *   DeepSeek: Digital cobalt blue (`#0f52ba`)
    *   Local Ollama: Glowing Emerald Green (`var(--green-profit)`)

---

## 9.5 Phase 9 Consolidated Checklist

| # | Task | Status |
| :--- | :--- | :--- |
| 1 | Create user schemas with secure JWT authentication endpoints | ☐ |
| 2 | Build encryption utility for encrypting/decrypting BYOK API keys (AES-256) | ☐ |
| 3 | Create integration modules for OpenAI, Anthropic, DeepSeek, and Ollama | ✅ Done |
| 4 | Map API keys conditionally from active user context in `agent_executor.py` | ☐ |
| 5 | Build the Settings keys portal in the React UI | ☐ |
| 6 | Create visual DeepSeek "Reasoning Steps" accordion panel in UI | ☐ |
| 7 | Upgrade dashboard layout to support full 6-agent concurrency colors | ✅ Done |
| 8 | Perform live manual scan with 5+ agents concurrently | ✅ Done |

---

> **Phase 9 is COMPLETE when:** Users can sign up, securely save their personal API keys, launch a concurrent stock query, and see all active agents (including DeepSeek with full reasoning steps and Local Ollama) respond instantly.
