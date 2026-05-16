from .connection import engine, SessionLocal, Base
from .models import Agent
from config import settings

def seed_agents():
    db = SessionLocal()
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)

        # Delete old agents and re-seed with correct providers
        existing = db.query(Agent).all()
        
        # If old agents exist with wrong providers, reset
        needs_reseed = False
        if existing:
            for a in existing:
                if a.name == "Grok" and a.provider == "xai":
                    needs_reseed = True
                    break
        
        if needs_reseed or db.query(Agent).count() == 0:
            # Clear old agents
            db.query(Agent).delete()
            db.commit()
            
            agents = [
                Agent(name="Gemini", provider="google", model_name="gemini-2.0-flash", cash_balance=settings.INITIAL_CAPITAL),
                Agent(name="Groq-Llama", provider="groq", model_name=settings.GROQ_MODEL, cash_balance=settings.INITIAL_CAPITAL),
            ]
            db.add_all(agents)
            db.commit()
            print("Successfully seeded 2 AI agents: Gemini + Groq-Llama")
        else:
            print("Agents already seeded correctly.")
    except Exception as e:
        print(f"Error seeding agents: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_agents()
