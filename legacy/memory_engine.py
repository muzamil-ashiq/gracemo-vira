#!/usr/bin/env python3
"""
GraceEMO Human-Like Memory & Dynamic Knowledgebase Engine
Provides:
1. Working Memory (Short-Term Episodic Buffer)
2. Long-Term Associative Memory (Persistent User Profiles, Relationships & Past Topics)
3. Cognitive Fact Extraction (Learns user names, departments, preferences, and discussions)
4. Dynamic Knowledgebase Semantic Search (RAG over campus files & live scraped knowledge)
"""

import os
import json
import time
import re
from datetime import datetime

MEMORY_FILE = "data/human_memory.json"
KNOWLEDGE_DIR = "data"

class HumanMemoryEngine:
    def __init__(self, memory_path=MEMORY_FILE):
        self.memory_path = memory_path
        self.current_user = "guest"
        self.working_memory = []  # Short-term buffer
        self.long_term_memory = self._load_memory()

    def _load_memory(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Notice: Initializing fresh memory ({e})")
        return {
            "users": {
                "sam_davi": {
                    "name": "Sam Davi",
                    "role": "Project Lead & Robotics Engineer",
                    "notes": ["Lead creator of GraceEMO humanoid robot", "Engineered hardware, sensors, and ROS 2 system"],
                    "relationship": "Creator",
                    "interactions_count": 1,
                    "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "dr_mohit_arora": {
                    "name": "Dr. Mohit Arora",
                    "role": "Faculty Mentor & Research Professor",
                    "notes": ["Spearheads AI & Autonomous Robotics research at LPU", "Mentored the student creation team"],
                    "relationship": "Mentor",
                    "interactions_count": 1,
                    "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            },
            "topics_discussed": [],
            "recent_events": []
        }

    def save_memory(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.long_term_memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def identify_or_create_user(self, text):
        """Extracts names like 'I am Rahul' or 'My name is Dr. Sharma' from user input."""
        name_match = re.search(r"\b(?:i am|my name is|this is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text, re.IGNORECASE)
        if name_match:
            raw_name = name_match.group(1).strip()
            user_key = raw_name.lower().replace(" ", "_")
            if user_key not in self.long_term_memory["users"]:
                self.long_term_memory["users"][user_key] = {
                    "name": raw_name,
                    "role": "Student / Guest",
                    "notes": [],
                    "relationship": "Visitor",
                    "interactions_count": 0,
                    "first_met": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            self.current_user = user_key
            self.long_term_memory["users"][user_key]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.long_term_memory["users"][user_key]["interactions_count"] += 1
            self.save_memory()
            return raw_name
        return None

    def store_interaction_memory(self, user_input, robot_output):
        """Stores key discussion memory in short-term buffer and extracts user insights."""
        # 1. Update working memory (buffer of last 10 turns)
        self.working_memory.append({
            "user": user_input,
            "robot": robot_output,
            "timestamp": time.time()
        })
        if len(self.working_memory) > 10:
            self.working_memory.pop(0)

        # 2. Check for personal facts to store in long-term memory
        if self.current_user in self.long_term_memory["users"]:
            usr = self.long_term_memory["users"][self.current_user]
            
            # Detect department/study area
            dept_match = re.search(r"\b(?:study|studying|in|from)\s+(cse|computer science|robotics|mechanical|business|btech|mtech|biotech)\b", user_input, re.IGNORECASE)
            if dept_match:
                dept_note = f"Studies {dept_match.group(1).upper()}"
                if dept_note not in usr["notes"]:
                    usr["notes"].append(dept_note)

            # Store significant interest
            if len(user_input) > 20 and not user_input.startswith("Who") and not user_input.startswith("What"):
                note_snippet = f"Discussed: {user_input[:80]}"
                if len(usr["notes"]) < 8 and note_snippet not in usr["notes"]:
                    usr["notes"].append(note_snippet)

            usr["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_memory()

    def detect_and_learn_correction(self, user_input):
        """
        Detects if the user is correcting an error or teaching a new fact.
        e.g. 'No that is wrong, Dr. Mittal is an MP in AAP'
             'Actually, the robotics lab is in block 38'
             'Correction: my name is Rahul'
             'Remember that LPU was founded in 2005'
        """
        text_lower = user_input.lower().strip()
        correction_triggers = [
            "no that is wrong", "that is wrong", "that's wrong", "that is incorrect", "that's incorrect",
            "you are wrong", "you're wrong", "actually", "correction:", "correction",
            "remember that", "keep in mind that", "note that", "not true", "it is not", "it isn't", "wrong"
        ]
        
        is_correction = any(trig in text_lower for trig in correction_triggers)
        if is_correction:
            # Clean up the corrected knowledge statement
            cleaned_fact = re.sub(r'^(no,? (that is|that\'s) (wrong|incorrect),?\s*|actually,?\s*|correction:?\s*|you are wrong,?\s*|remember that\s*|keep in mind that\s*|wrong,?\s*)', '', user_input, flags=re.IGNORECASE).strip()
            
            if len(cleaned_fact) > 4:
                if "corrections" not in self.long_term_memory:
                    self.long_term_memory["corrections"] = []
                
                correction_entry = {
                    "raw_correction": user_input,
                    "learned_fact": cleaned_fact,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.long_term_memory["corrections"].append(correction_entry)
                self.save_memory()
                
                # Also append to dynamic knowledge file for persistence across fine-tuning
                corrections_file = "data/knowledgebase/dynamic_corrections.json"
                os.makedirs(os.path.dirname(corrections_file), exist_ok=True)
                existing = []
                if os.path.exists(corrections_file):
                    try:
                        with open(corrections_file, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    except Exception:
                        existing = []
                existing.append(correction_entry)
                with open(corrections_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)

                print(f"💡 [Real-Time Model Learning] Learned new correction: '{cleaned_fact}'")
                return cleaned_fact
        return None

    def get_memory_context(self, current_input):
        """Constructs human-like memory injection for the AI Vice Chancellor."""
        context_parts = []

        # 1. Learned Real-Time Corrections (Top Priority)
        if "corrections" in self.long_term_memory and self.long_term_memory["corrections"]:
            recent_corrections = [c["learned_fact"] for c in self.long_term_memory["corrections"][-4:]]
            context_parts.append(f"[PRIORITY REAL-TIME CORRECTIONS: {'; '.join(recent_corrections)}]")

        # 2. Check if user is known
        self.identify_or_create_user(current_input)

        if self.current_user != "guest" and self.current_user in self.long_term_memory["users"]:
            usr = self.long_term_memory["users"][self.current_user]
            name = usr.get("name", "Friend")
            role = usr.get("role", "Visitor")
            notes = ", ".join(usr.get("notes", []))
            count = usr.get("interactions_count", 1)
            
            context_parts.append(f"[HUMAN MEMORY: You are speaking with {name} ({role}). You have spoken {count} times before. Known details: {notes if notes else 'None'}. Greet or acknowledge them warmly as Vice Chancellor.]")

        # 3. Add recent working memory context if relevant
        if len(self.working_memory) > 0:
            last_turn = self.working_memory[-1]
            context_parts.append(f"[RECENT CONVERSATION CONTEXT: User previously asked about '{last_turn['user'][:60]}']")

        return "\n".join(context_parts)

class DynamicKnowledgebase:
    """Instant semantic retrieval across campus files and live scraped data."""
    def __init__(self, data_folder=KNOWLEDGE_DIR):
        self.data_folder = data_folder
        self.knowledge_documents = self._load_documents()

    def _load_documents(self):
        docs = []
        if not os.path.exists(self.data_folder):
            return docs

        # First load clean text files and structured facts
        priority_files = ["india_and_world_facts.json", "3-Important-people.txt", "4-creators.txt", "2-about-college.txt", "5-cources.txt", "7-facalities.txt"]
        all_files = priority_files + [f for f in os.listdir(self.data_folder) if f not in priority_files and not f.startswith("scraped_")]

        for fname in all_files:
            fpath = os.path.join(self.data_folder, fname)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    if fname.endswith(".json"):
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "facts" in item:
                                    docs.append(f"[{item.get('topic', 'Fact')}]: {item['facts']}")
                                else:
                                    docs.append(str(item))
                        elif isinstance(data, dict):
                            for k, v in data.items():
                                docs.append(f"{k}: {v}")
                    else:
                        content = f.read()
                        paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 20]
                        docs.extend(paragraphs)
            except Exception:
                continue
        return docs

    def query_knowledge(self, user_query, top_k=2):
        """Finds most relevant facts from the knowledgebase using entity and keyword relevance."""
        if not user_query or not self.knowledge_documents:
            return ""

        # Normalize common abbreviations
        norm_query = user_query.lower()
        norm_query = re.sub(r'\bcm\b', 'chief minister', norm_query)
        norm_query = re.sub(r'\bpm\b', 'prime minister', norm_query)
        norm_query = re.sub(r'\bvc\b', 'vice chancellor', norm_query)

        query_words = set(re.findall(r"\w+", norm_query))
        stop_words = {"what", "who", "where", "when", "how", "is", "are", "the", "a", "an", "tell", "me", "about", "in", "of", "and", "do", "you", "from", "party", "which", "our"}
        meaningful_words = query_words - stop_words

        if not meaningful_words:
            return ""

        scored_docs = []
        for doc in self.knowledge_documents:
            doc_lower = doc.lower()
            # Exact phrase bonus
            score = 0
            if "tamil nadu" in norm_query and "tamil nadu" in doc_lower:
                score += 5
            if "pro-chancellor" in norm_query or "pro chancellor" in norm_query:
                if "pro-chancellor" in doc_lower or "pro chancellor" in doc_lower:
                    score += 5
            if "ashok" in norm_query and "ashok" in doc_lower:
                score += 5
            if ("creator" in norm_query or "built" in norm_query) and ("sam davi" in doc_lower or "creators" in doc_lower):
                score += 5

            # Word overlap score
            score += sum(2 for w in meaningful_words if w in doc_lower)
            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_results = [doc for _, doc in scored_docs[:top_k]]

        if top_results:
            return "[RETRIEVED GROUND-TRUTH FACTS:\n" + "\n---\n".join(top_results) + "\n]"
        return ""

# Global singletons for memory & knowledgebase
MEMORY_ENGINE = HumanMemoryEngine()
KNOWLEDGE_BASE = DynamicKnowledgebase()

if __name__ == "__main__":
    print("Testing Human Memory Engine...")
    print("1. Identifying User:")
    MEMORY_ENGINE.identify_or_create_user("Hello, I am Dr. Sharma from the Mechanical Department.")
    print("Memory Context:", MEMORY_ENGINE.get_memory_context("Do you have research labs?"))

    print("\n2. Querying Dynamic Knowledgebase:")
    facts = KNOWLEDGE_BASE.query_knowledge("What sports facilities are at Shanti Devi Mittal stadium?")
    print("Facts:", facts)
