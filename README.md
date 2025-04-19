# Notes for Goats

A personal note-taking application designed for professionals to organize structured notes about people, projects, and daily events.

<details>
<summary>📸 Behold, screenshots! (click to expand)</summary>

![Home Screen](screenshots/home.png)
![Notes](screenshots/notes.png)
![Entities](screenshots/entities.png)
![Relationships](screenshots/relationships.png)
![Backups](screenshots/backups.png)
![AI](screenshots/ai.png)

</details>

## Installation

### Option 1: Using Docker (Recommended)

The easiest way to get started is with Docker:

1. **Prerequisites**
   - [Docker](https://www.docker.com/get-started)
   - [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

2. **Setup and Launch**
   
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/notes-for-goats.git
   cd notes-for-goats
   
   # Set up environment variables (including OpenAI API key)
   make env
   
   # Build and start the application
   docker-compose up -d
   
   # Create an admin user (first time only)
   docker-compose exec web python notes_for_goats/manage.py createsuperuser
   ```

3. **Access the application**
   - Main app: http://localhost:8000/
   - Admin interface: http://localhost:8000/admin/

4. **Stop the application**
   
   ```bash
   docker-compose down
   ```

### Option 2: Standard Installation

If you prefer to run directly on your machine:

1. **Prerequisites**
   - Python 3.8+

2. **Setup**
   
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/notes-for-goats.git
   cd notes-for-goats
   
   # Set up environment variables (including OpenAI API key)
   make env
   
   # Create and activate a virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up the database and create admin user
   python manage.py migrate
   python manage.py createsuperuser
   
   # Run the development server
   python manage.py runserver
   ```

3. **Access the application**
   - Main app: http://127.0.0.1:8000/
   - Admin interface: http://127.0.0.1:8000/admin/

### Setting Up Environment Variables

Notes for Goats uses a `.env` file to store configuration settings. Use our convenient setup script to create this file:

1. **Run the setup command**
   
   ```bash
   make env
   ```

2. **Follow the prompts**
   - For each variable, you'll see the default value
   - Press Enter to accept the default or type a new value
   - For the SECRET_KEY, a secure random key will be generated automatically
   - **When prompted for OPENAI_API_KEY**, enter your OpenAI API key
     (Get one at https://platform.openai.com/api-keys if you don't have one)

3. **The script creates a `.env` file** containing all your settings

Your OpenAI API key is required for the Ask AI feature. If you don't have one yet, you can still run the application, but the AI features won't work.

## How to Use Notes for Goats

### Workspaces

Workspaces are like separate notebooks that help you organize different areas of your life:

- Create separate workspaces for different jobs, projects, or contexts
- Each workspace has its own entities, notes, and relationships
- Switch between workspaces using the dropdown in the navigation bar

### Entities

Entities are the core building blocks in Notes for Goats:

1. **What are Entities?**
   - People (colleagues, clients, team members)
   - Projects (initiatives, products, assignments)
   - Teams (departments, working groups, committees)

2. **Creating Entities**
   - Navigate to "Entities" and click "New Entity"
   - Select a type (Person, Project, or Team)
   - Enter a name and optional details
   - Add tags to make entities easier to find

3. **Using Entities**
   - View all entities from the Entities page
   - Click on any entity to see its details and related notes
   - Filter entities by type or search by name/tags

### Notes

Notes let you capture information while automatically connecting to relevant entities:

1. **Creating Notes**
   - Navigate to "Notes" and click "New Note"
   - Give your note a title and content
   - Use #hashtags to reference entities (e.g., "Meeting with #Alice about #ProjectX")

2. **Entity References**
   - Any entity name preceded by # will be detected as a reference
   - Referenced entities appear at the bottom of the note
   - Click on a referenced entity to view its details

3. **Viewing Notes**
   - Browse all notes from the Notes page
   - Filter notes by date or search by content
   - View notes related to specific entities from their detail pages

### Relationships

Relationships help you track connections between entities:

1. **Relationship Types**
   - Define custom relationship types (e.g., "Reports To", "Works On")
   - Set whether relationships are directional (one-way) or bidirectional
   - Configure inverse names for directional relationships (e.g., "Reports To" ↔ "Manages")

2. **Creating Relationships**
   - From an entity's detail page, click "Add Relationship"
   - Select the relationship type and the related entity
   - Add optional details about the relationship

3. **Relationship Inference**
   - Set up rules to automatically create relationships based on patterns
   - Example: When two people work on the same project, create a "Collaborator" relationship
   - Automatically maintain your organizational structure with minimal effort

### Ask AI

The Ask AI feature lets you interact with your notes using natural language:

1. **Accessing Ask AI**
   - From any workspace, click on the "Ask AI" button
   - You'll see a form where you can enter your question

2. **How It Works**
   - The AI analyzes your notes, entities, and relationships within the current workspace
   - It uses this context to provide informed answers to your questions
   - The AI response is generated using OpenAI's language models

3. **Example Questions**
   - "Summarize what I know about Project X"
   - "What were the key points from my meeting with Alice last week?"
   - "What relationships exist between the Marketing team and the Sales team?"
   - "Find all notes mentioning budget concerns"

4. **Limitations**
   - Responses are based only on the information in your notes
   - The AI cannot access external information or your personal knowledge
   - Quality of responses depends on the detail and organization of your notes

Note: The Ask AI feature requires a valid OpenAI API key to be configured in your `.env` file.

## Data Backup and Migration

Keep your valuable notes safe:

### Backup Options

1. **Export Workspaces (Recommended)**
   - From the Workspace Settings page, click "Export Workspace"
   - Saves all workspace data as a JSON file that can be imported later

2. **Direct Database Backup**
   - For standard installations: Copy the `db.sqlite3` file to a secure location
   - For Docker installations:
     ```