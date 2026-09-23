from .connection import engine, SessionLocal, Base
from .models import Agent
from config import settings

def seed_agents():
    db = SessionLocal()
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)

        # Purge existing openrouter/github/deepseek agents and their dependencies —
        # these providers have been removed from the app entirely.
        purged_agents = db.query(Agent).filter(Agent.provider.in_(("openrouter", "github", "deepseek"))).all()
        if purged_agents:
            from database.models import Trade, Position, DailyPerformance, AIResponse, AgentDailyStrategy
            for agent in purged_agents:
                db.query(Position).filter(Position.agent_id == agent.id).delete()
                db.query(Trade).filter(Trade.agent_id == agent.id).delete()
                db.query(DailyPerformance).filter(DailyPerformance.agent_id == agent.id).delete()
                db.query(AIResponse).filter(AIResponse.agent_id == agent.id).delete()
                db.query(AgentDailyStrategy).filter(AgentDailyStrategy.agent_id == agent.id).delete()
                db.delete(agent)
            db.commit()

        # Delete old agents and re-seed with correct providers
        existing_agents = {a.name: a for a in db.query(Agent).all()}
        
        agents_to_add = []
        if "Gemini" not in existing_agents:
            agents_to_add.append(Agent(name="Gemini", provider="google", model_name=settings.GEMINI_MODEL, cash_balance=settings.INITIAL_CAPITAL))
        if "Groq-Llama" not in existing_agents:
            agents_to_add.append(Agent(name="Groq-Llama", provider="groq", model_name=settings.GROQ_MODEL, cash_balance=settings.INITIAL_CAPITAL))
        if "Local-Ollama" not in existing_agents:
            agents_to_add.append(Agent(name="Local-Ollama", provider="ollama", model_name=settings.OLLAMA_MODEL, cash_balance=settings.INITIAL_CAPITAL))
            
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
