# Quick Start Guide

Get RTC Backend running in under 5 minutes.

## 🚀 Fastest Path (No API Keys)

```bash
cd backend
pip install -e .
python -c "from app.db.sqlite import init_db; init_db()"
uvicorn app.main:app --reload
```

Open: http://localhost:8000/docs

**What works**: Database, health checks, article viewing  
**What doesn't**: Vectors, insights, automated ingestion

---

## ⚡ Full Setup (With OpenAI)

```bash
# 1. Install with vectors
cd backend
pip install -e ".[vectors]"

# 2. Configure
echo 'OPENAI_API_KEY=sk-your-key-here' > .env

# 3. Initialize
python -c "from app.db.sqlite import init_db; init_db()"

# 4. Run
uvicorn app.main:app --reload
```

Open: http://localhost:8000/health

**Everything works!** ✓

---

## 📋 Using Makefile

```bash
make install-vectors    # Install dependencies
make init-db           # Initialize database
make dev              # Run development server
```

---

## 🧪 Test It Works

```bash
# Check health
curl http://localhost:8000/health

# Run tests
pytest

# Using CLI
python cli.py health
python cli.py stats
```

---

## 📚 Next Steps

1. **Add scheduled ingestion**: See README.md → "Scheduling with Cron"
2. **Configure search API**: Set `SEARCH_API_KEY` in `.env`
3. **Deploy**: See README.md → "Production Checklist"

---

## 🆘 Troubleshooting

**"Vector operations unavailable"**
```bash
pip install -e ".[vectors]"
export OPENAI_API_KEY=sk-...
```

**"Module not found"**
```bash
pip install -e .  # Install in editable mode
```

**"Port 8000 in use"**
```bash
uvicorn app.main:app --port 8001
```

---

## 📖 Full Documentation

- **Complete setup**: `SETUP.md`
- **API reference**: http://localhost:8000/docs (when running)
- **Architecture**: `README.md`
- **Changes**: `CHANGELOG.md`
- **Refactor details**: `REFACTOR_SUMMARY.md`

---

**That's it!** 🎉

For questions, check the docs or run `make help`.

