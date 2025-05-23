# Notes for Goats

A personal note-taking application designed for professionals to organize structured notes about people, projects, and daily events.

## How to Access

This web app is currently deployed to https://notes.emilyflam.be. It is hidden behind basic authentication (implemented via Caddy). Feel free to contact me for the login, or honestly just guess a few times and you'll probably get it. The deployed app is for demonstration purposes only - because this app was coded without a particularly security-first mindset, users are strongly encouraged to use the app via local deployment (see below).

If you choose to use OpenAI for the extremely sophisticated AI features in this app, be mindful of the data you're giving them. I mean, they probably already have all of your personal information anyway, but you should at least ponder the consequences of your actions.

## Screenshots

<details>
<summary>📸 Screenshots (click to expand)</summary>

![Home Screen](screenshots/home.png)
![Notes](screenshots/notes.png)
![Entities](screenshots/entities.png)
![Relationships](screenshots/relationships.png)
![Backups](screenshots/backups.png)
![AI](screenshots/ai.png)

</details>

## Installation

### Option 1: Using Docker (Recommended)

1. **Prerequisites**
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

2. **Setup and Launch**

   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/notes-for-goats.git
   cd notes-for-goats
   
   # Set up environment variables
   make env

   # Build and start the application
   make build
   make up

   # Create an admin user (first time only)
   make superuser
   ```

3. **Access**
   - Main app: http://localhost:8000/
   - Admin interface: http://localhost:8000/admin/

### Option 2: Standard Installation

1. **Prerequisites**
- Python 3.8+ 

2. **Setup**

   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/notes-for-goats.git
   cd notes-for-goats
   
   # Set up environment variables
   make env

   # Clone the repository
   git clone https://github.com/yourusername/notes-for-goats.git
   cd notes-for-goats

   # Install dependencies
   pip install -r requirements.txt

   # Set up the database and create admin user
   python manage.py migrate
   python manage.py createsuperuser

   # Run the development server
   python manage.py runserver
   ```

## Setting Up AI Features

Notes for Goats supports two AI backends: OpenAI (default, faster with better results) and local models via Ollama (free alternative with complete privacy).

### Option 1: OpenAI API (Recommended)

For the best experience with powerful AI capabilities:

1. **Get an API key** from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

2. **Configure Notes for Goats**
   
   When running `make env`, enter your OpenAI API key when prompted.

3. **Toggle in the UI**
   
   You can switch between OpenAI and local models directly in the Ask AI interface.

### Option 2: Local AI with Ollama (Free Alternative)

Run AI features locally with complete privacy and no usage costs:

1. **Install Ollama**
   
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Windows: Download from ollama.com/download/windows
   ``` 

2. **Start the ollama service**

   ```bash
   ollama run llama3
   ```

3. **Download a model**
   
   ```bash
   # Download Llama 3 (recommended)
   ollama pull llama3
   ```

3. **Configure Notes for Goats**
   
   When running `make env`, set these values:
   ```
   LOCAL_LLM_URL=http://localhost:11434
   LOCAL_LLM_MODEL=llama3
   ```

## How to Use Notes for Goats

### Workspaces

Organize your notes into separate contexts:

- Create workspaces for different projects, roles, or areas of focus
- Each workspace has its own entities, notes, and relationships
- Switch between workspaces via the navigation bar

### Entities

The building blocks of your knowledge base:

- **Types**: People, Projects, and Teams
- **Creation**: Navigate to "Entities" → "New Entity" → select type
- **Usage**: View all entities, search by name/tags, or filter by type

### Notes

Record information while automatically linking to entities:

- **Create**: Add new notes with title and content
- **Link**: Use #hashtags to reference entities (e.g., "Meeting with #Alice about #ProjectX")
- **Browse**: Filter notes by date, search content, or view by related entity

### Relationships

Track connections between entities:

- Create relationship types (e.g., "Reports To", "Works On")
- Add relationships from entity detail pages
- Set up inference rules for automatic relationship creation

### Ask AI

Interact with your notes using natural language:

1. Click "Ask AI" from any workspace
2. Type your question
3. Choose between local LLM or OpenAI
4. Get answers based on your notes, entities, and relationships

**Example Questions:**
- "Summarize what I know about Project X"
- "What were the key points from my meeting with Alice last week?"
- "What connections exist between the Marketing and Sales teams?"

**Privacy Note**: By default, queries are processed using OpenAI in the cloud. For complete privacy, switch to the local LLM option which keeps all data on your computer.

## Data Backup and Migration

Keep your valuable notes safe:

1. **Export Workspaces**
   - Workspace Settings → Export Workspace → Save JSON file

2. **Database Backup**
   - Standard installation: Copy `db.sqlite3`
   - Docker: 
     ```bash
     docker-compose exec web bash -c "cd notes_for_goats && python manage.py export_data"
     ```

## Advanced AI Features

Notes for Goats includes advanced AI capabilities to help you get more out of your personal knowledge base.

### Retrieval Augmented Generation (RAG)

When using OpenAI's models, Notes for Goats implements RAG to provide more accurate and relevant answers:

#### How RAG Works in Notes for Goats

1. **Vector Embeddings**: Each note and entity is processed into a vector embedding that captures its semantic meaning.

2. **Query Processing**: When you ask a question, the system:
   - Converts your query into a similar vector embedding
   - Compares it against all notes and entities in your workspace
   - Identifies the most relevant content based on semantic similarity
   - Sends only the most relevant information to the AI model

3. **Context-Aware Responses**: Instead of processing your entire database (which could exceed token limits), the AI receives only the most relevant information to your specific question.

4. **Privacy & Efficiency**: This approach:
   - Reduces token usage (and thus API costs)
   - Improves response quality by focusing on relevant information
   - Maintains workspace isolation (data from other workspaces is never included)

#### RAG Availability

- **OpenAI Mode**: RAG is automatically enabled when using OpenAI models
- **Local LLM Mode**: Currently uses full context (no RAG) due to embedding requirements
- **Token Usage**: When using RAG, you'll see a "RAG Active" indicator showing reduced token usage

#### Example

When you ask "What did Alice think about the marketing proposal?", instead of sending all notes and entities:

1. The system identifies notes mentioning both Alice and marketing proposals
2. Only sends those specific notes as context to the AI
3. Generates a focused response based on just the relevant information

This approach provides more accurate answers while keeping token usage reasonable, even in large workspaces.

## Troubleshooting AI Features

### OpenAI Issues

- Verify your API key is valid
- Check for rate limiting or quota issues
- Ensure your OpenAI account has billing set up

### Local LLM Issues

If Ollama isn't working:

- Verify it's running: `ollama list`
- Test API directly:
  ```bash
  curl -X POST http://localhost:11434/api/generate \
    -H "Content-Type: application/json" \
    -d '{"model":"llama3","prompt":"Hello","stream":false}'
  ```
- Check `LOCAL_LLM_URL` doesn't include `/api` at the end
- For best performance: 16GB+ RAM, GPU or Apple Silicon recommended

## Planned Features

- RAG-based AI for more efficient querying of large note collections
- Google Calendar integration
- Note templates
- Visual relationship graphs

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

*Notes for Goats: Because you're worth it* 🐐📝