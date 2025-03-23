from pymongo.collection import Collection
from pymongo import MongoClient
import os
import pandas as pd
from bson import ObjectId
import numpy as np
from util.logger_config import logger
from bs4 import BeautifulSoup
import re


client = MongoClient(os.getenv('MONGO_URI'))
karma_watch = client.anime.karma_watch
    # Entries larger than 48 hours


class AnimeBanner:

    def __init__(self, title, image_url, mal_id, html_path):
        self.title = title
        self.image_url = image_url
        self.mal_id = mal_id
        self.html_path = html_path
        
    def get_html_from_file(self, file_path):
        if not file_path:
            file_path = self.html_path
        with open(file_path, 'r', encoding='utf-8') as file:
            self.html_content = file.read()

    def save_html_to_file(self, file_path, content):
        if not file_path:
            file_path = self.html_path
        if not content:
            content = self.get_html_from_file(file_path)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

    def replace_link_in_a_tag(self, html):
        if not html:
            html = self.html_content
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all <div> elements with class 'details' and style attribute
        for div in soup.find_all('div', class_='details', style=True):
            # Extract background-image URL using regex
            match = re.search(r'background-image:\s*url\((.*?)\)', div['style'])
            if match:
                bg_image_url = match.group(1).strip('()"\'')  # Clean the URL from any quotes
                
                # Find <a> tag with class 'external-link' as direct child of this div
                a_tag = div.find('a', class_='external-link', recursive=False)
                
                if not a_tag:
                    # Create new <a> tag and insert it as first element inside div
                    new_a = soup.new_tag('a', href=bg_image_url, 
                                    **{'class': 'external-link', 
                                        'target': '_blank'})
                    div.insert(1, new_a)  # Insert after the first element
                elif a_tag['href'] != bg_image_url:
                    # Update existing <a> tag's href if different
                    a_tag['href'] = bg_image_url
        self.fixed_html = str(soup)
        return self.fixed_html
        


def get_uncleaned_entries(karma_watch: Collection, year = 2025, season = 'winter') -> list:
    entries = list(karma_watch.find(
            {
                '$expr': {
                    '$and': [
                    {'$lte': [{'$size': '$hourly_karma'}, 47]},
                    {'year': year},
                    {'season': season}
                    ]
                }
                
            },
            {
                '_id': 1,
                'hourly_karma': 1,
                'mal_id': 1,
                'reddit_id': 1

            }
        ))
    return entries if entries else []

def normalize_entry(entries: list[dict]) -> list:
    new_entries = []
    for entry in entries:
        logger.info(f"Processing entry: {entry.get('title')} EP {entry.get('episode')} {entry['reddit_id']}")
        _id = ObjectId(entry['_id'])
        hourly_karma: list[dict] = entry['hourly_karma']
        df = pd.DataFrame(hourly_karma)
        df.columns = ['hours', 'karma']
        # Rename columns to more descriptive names
        df.columns = ['hours', 'karma']
        
        # Round hours to nearest integer
        df['hour_rounded'] = df['hours'].round().astype(int)
        
        # Create a complete range of hours from 1 to 48
        all_hours = pd.DataFrame({'hour_rounded': range(1, 49)})
        
        # For each hour, get the exact karma value from the last entry for that hour
        # This preserves the exact values rather than averaging them
        hour_karma = df.sort_values('hours').groupby('hour_rounded').last()[['karma']].reset_index()
        
        # Merge with complete range to ensure all hours are present
        result = pd.merge(all_hours, hour_karma, on='hour_rounded', how='left')
        
        
        # If there are any missing hours (NaN values), fill them with nearest neighbor
        if result['karma'].isna().any():
            for idx, row in result[result['karma'].isna()].iterrows():
                try:
                    hour = row['hour_rounded']
                    
                    # Find all existing hours
                    existing_hours = result.dropna(subset=['karma'])['hour_rounded'].values
                    logger.debug(f"Existing hours: {existing_hours}")
                    
                    # Calculate distances to all existing hours
                    distances = np.abs(existing_hours - hour)
                    
                    # Find the nearest hour
                    nearest_hour = existing_hours[np.argmin(distances)]
                    
                    
                    # Get the karma value from the nearest hour
                    nearest_value = result.loc[result['hour_rounded'] == nearest_hour, 'karma'].iloc[0]
                    logger.debug(f"Nearest hour: {nearest_hour} Nearest value: {nearest_value}")
                    
                    # Fill the missing value
                    result.loc[idx, 'karma'] = nearest_value
                except ValueError:
                    logger.error(f"Error processing entry: {entry.get('title')} EP {entry.get('episode')} {entry['reddit_id']}")
                    continue
                except Exception as e:
                    logger.critical(f"Critical error processing entry: {entry.get('title')} EP {entry.get('episode')} {entry['reddit_id']}")
                    logger.exception(e)
                    continue
        
        # Create more readable output
        result.columns = ['hour', 'karma']
        cleaned_hourly_karma = result.to_dict(orient='records')
        new_entry = {'_id': _id, 'hourly_karma': cleaned_hourly_karma}
        new_entries.append(new_entry)
    return new_entries

def update_karma_watch(karma_watch: Collection, fixed_entries: list[dict]):
    for entry in fixed_entries:
        _id = entry['_id']
        hourly_karma = entry['hourly_karma']
        karma_watch.update_one({'_id': _id}, {'$set': {'hourly_karma': hourly_karma}})
    
        
