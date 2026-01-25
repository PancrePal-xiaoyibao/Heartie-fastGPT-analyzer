import re
import pandas as pd
from datetime import datetime

class LogParser:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.data = []

    def parse(self):
        """
        Parses the log file and extracts Q&A pairs.
        Assumes sequential logging: Query comes first, then Reply.
        """
        print(f"Parsing log file: {self.log_file_path}")
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: File not found {self.log_file_path}")
            return pd.DataFrame()

        current_entry = {}
        
        # Regex patterns
        # [INFO][2025-05-31 14:53:42]...
        time_pattern = r'\[INFO\]\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]'
        
        # [CHATGPT] query=...
        query_pattern = r'\[CHATGPT\] query=(.*)'
        
        # [gewechat] Do send text to ...: ... (reply content)
        reply_start_pattern = r'\[gewechat\] Do send text to .*?: (.*)'
        
        for i, line in enumerate(lines):
            # Extract timestamp
            time_match = re.search(time_pattern, line)
            timestamp = time_match.group(1) if time_match else None
            
            # Check for User Query
            query_match = re.search(query_pattern, line)
            if query_match:
                # If we have a pending entry (query without reply), we might save it as unanswered or just overwrite
                if current_entry.get('query'):
                    # Discard previous unanswered query or handle as needed
                    pass
                
                current_entry = {
                    'timestamp': timestamp,
                    'query': query_match.group(1).strip(),
                    'reply': None
                }
                continue

            # Check for Bot Reply Start
            reply_match = re.search(reply_start_pattern, line)
            if reply_match and current_entry.get('query'):
                # Found a potential reply block
                reply_content = [reply_match.group(1).strip()]
                
                # Check if this reply belongs to the current query? 
                # In simple sequential logs, we assume yes.
                
                # Read subsequent lines until next log header or empty line
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    # Stop if next line is a log header
                    if re.match(r'\[(INFO|WARNING|ERROR)\]', next_line):
                        break
                    reply_content.append(next_line.strip())
                    j += 1
                
                current_entry['reply'] = '\n'.join(reply_content).strip()
                
                # Ignore "received image" processing logs if they don't look like real answers
                # But here we assume all [gewechat] Do send text to... are answers.
                
                # Add valid entry
                self.data.append(current_entry)
                current_entry = {} # Reset
                
        df = pd.DataFrame(self.data)
        # Clean up column names to match what XiaoXinBaoDataProcessor expects or at least be useful
        if not df.empty:
            df.rename(columns={'query': 'dialogue_content', 'reply': 'bot_reply'}, inplace=True)
            # Add dummy columns if needed for strict compatibility, or just let existing processor handle flexible columns
            df['source'] = 'log_parser'
            
        return df

if __name__ == '__main__':
    import sys
    import os
    
    input_file = 'input/xyanb.yaml'
    output_file = 'input/parsed_logs.csv'
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
        
    parser = LogParser(input_file)
    df = parser.parse()
    
    if not df.empty:
        print(f"Parsed {len(df)} Q&A pairs.")
        print(df.head())
        df.to_csv(output_file, index=False)
        print(f"Saved to {output_file}")
    else:
        print("No data parsed.")
