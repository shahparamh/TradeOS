from .connection import engine, SessionLocal, Base
from .models import Agent
from config import settings

def seed_agents():
    db = SessionLocal()
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)

        # Delete old agents and re-seed with correct providers
        existing_agents = {a.name: a for a in db.query(Agent).all()}
        
        agents_to_add = []
        if "Gemini" not in existing_agents:
            agents_to_add.append(Agent(name="Gemini", provider="google", model_name=settings.GEMINI_MODEL, cash_balance=settings.INITIAL_CAPITAL))
        if "Groq-Llama" not in existing_agents:
            agents_to_add.append(Agent(name="Groq-Llama", provider="groq", model_name=settings.GROQ_MODEL, cash_balance=settings.INITIAL_CAPITAL))
        if "Local-Ollama" not in existing_agents:
            agents_to_add.append(Agent(name="Local-Ollama", provider="ollama", model_name=settings.OLLAMA_MODEL, cash_balance=settings.INITIAL_CAPITAL))
        if "OpenRouter" not in existing_agents:
            agents_to_add.append(Agent(name="OpenRouter", provider="openrouter", model_name="openrouter/free", cash_balance=settings.INITIAL_CAPITAL))
            
        if agents_to_add:
            db.add_all(agents_to_add)
            db.commit()
            print(f"Successfully added {len(agents_to_add)} new AI agents.")
        else:
            print("Agents already seeded correctly.")
    except Exception as e:
        print(f"Error seeding agents: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_agents()
