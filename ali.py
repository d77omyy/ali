import requests
from bs4 import BeautifulSoup
import json
import re
import time
import random

def search_aliexpress(product_name):
    # Prepare the search URL
    base_url = "https://www.aliexpress.com/w/wholesale-"
    search_url = f"{base_url}{product_name.replace(' ', '-')}.html"
    print("Searching:", search_url)
    
    # Send request with improved headers - adding language preferences for English
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.aliexpress.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Cookie": "aep_usuc_f=site=glo&c_tp=USD&region=US&b_locale=en_US"
    }
    
    try:
        # Add a small delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))
        response = requests.get(search_url, headers=headers, timeout=60)
        
        if response.status_code != 200:
            print(f"Failed to retrieve data. Status code: {response.status_code}")
            return None
        
        # Check if response is in English by looking at some keywords
        if not is_english(response.text):
            print("Response may not be in English. Trying with more explicit language parameters...")
            return search_with_explicit_language(product_name)
        
        # Try to extract JSON data from the page
        json_data = extract_json_data(response.text)
        if json_data:
            result = process_json_data(json_data, search_url)
            if result:
                return result
        
        # Fallback to traditional parsing if JSON extraction fails
        return parse_html(response.text, search_url)
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def is_english(html_content):
    # Simple check for English content
    english_markers = ['product', 'price', 'shipping', 'result', 'search', 'item']
    return any(marker in html_content.lower() for marker in english_markers)

def search_with_explicit_language(product_name):
    # Force English language by adding parameters to URL
    base_url = "https://www.aliexpress.com/wholesale"
    params = {
        "SearchText": product_name,
        "g": "y",  # For wholesale items
        "SortType": "default",
        "needQuery": "n", 
        "page": 1,
        "isRefine": "y"
    }
    
    url = f"{base_url}?{requests.compat.urlencode(params)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "aep_usuc_f=site=glo&c_tp=USD&region=US&b_locale=en_US; xman_us_f=x_locale=en_US&x_l=0"
    }
    
    try:
        time.sleep(random.uniform(1, 3))
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code != 200:
            print(f"Failed to retrieve data with explicit language. Status code: {response.status_code}")
            return None
        
        json_data = extract_json_data(response.text)
        if json_data:
            return process_json_data(json_data, url)
        
        return parse_html(response.text, url)
        
    except Exception as e:
        print(f"Error with explicit language search: {e}")
        return None

def extract_json_data(html_content):
    try:
        # Look for multiple JSON data patterns that AliExpress might use
        json_patterns = [
            r'window\.__INIT_DATA__\s*=\s*({.*?});',
            r'window\.__data\s*=\s*({.*?});',
            r'data\s*:\s*({.*?})\s*[,;]',
            r'window\.runParams\s*=\s*({.*?});',
            r'"items"\s*:\s*(\[.*?\])',
            r'"productList"\s*:\s*(\[.*?\])'
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                json_str = match.group(1)
                try:
                    data = json.loads(json_str)
                    return data
                except json.JSONDecodeError:
                    continue
                
        # If no success with patterns, try to find any large JSON blocks
        json_candidate_pattern = r'({[\s\S]*?"products"[\s\S]*?})'
        match = re.search(json_candidate_pattern, html_content)
        if match:
            try:
                # Try to sanitize and parse JSON
                json_str = match.group(1)
                # Fix common JSON format issues
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                pass
                
        # Additional pattern specifically for aliexpress product data
        module_pattern = r'window\._init_data_\s*=\s*({.*?});\s*</script>'
        match = re.search(module_pattern, html_content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return data
            except json.JSONDecodeError:
                pass
                
        return None
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return None

def process_json_data(data, original_url):
    try:
        # Print data structure for debugging
        print("JSON data found. Attempting to extract product information...")
        
        # Enhanced JSON navigation to find products
        products = None
        
        # Check various paths where product data might be located
        if isinstance(data, list) and len(data) > 0:
            products = data
        elif isinstance(data, dict):
            # Try different paths where products might be stored
            possible_paths = [
                ['pageModule', 'resultList'],
                ['items'],
                ['products'],
                ['data', 'products'],
                ['data', 'items'],
                ['result', 'products'],
                ['data', 'root', 'fields', 'productsFeed', 'products'],
                ['data', 'root', 'fields', 'items']
            ]
            
            for path in possible_paths:
                current = data
                valid_path = True
                
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        valid_path = False
                        break
                
                if valid_path and isinstance(current, list) and len(current) > 0:
                    products = current
                    print(f"Found products in path: {path}")
                    break
        
        if not products:
            # Check if we have a direct mods structure that AliExpress sometimes uses
            if isinstance(data, dict) and 'mods' in data:
                mods = data['mods']
                if isinstance(mods, dict) and 'itemList' in mods:
                    item_list = mods['itemList']
                    if isinstance(item_list, dict) and 'content' in item_list:
                        products = item_list['content']
                        print("Found products in mods.itemList.content")
        
        if not products:
            print("Could not find product data in JSON")
            # Additional debugging: print top-level keys
            if isinstance(data, dict):
                print(f"Top-level keys: {list(data.keys())}")
            return None
        
        # Get the first product
        product = products[0]
        
        # Print product keys for debugging
        if isinstance(product, dict):
            print(f"Product keys: {list(product.keys())}")
        
        # Extract product details with better error handling
        name = extract_value(product, ['title', 'name', 'productTitle', 'subject', 'item_title', 'product_title'], 'No name found')
        
        # Price extraction with multiple possible paths
        price = extract_value(product, 
                             ['price.formattedPrice', 'price.minPrice', 'price.maxPrice', 'price', 'minPrice', 'maxPrice',
                              'price_formatted', 'formatCurrency', 'current_price', 'salePrice', 'sku_price'], 
                             'No price found')
        
        # Handle price if it's a dictionary
        if isinstance(price, dict):
            for key in ['formattedPrice', 'formattedValue', 'minPrice', 'value', 'text', 'formatted_price']:
                if key in price:
                    price = price[key]
                    break
        
        # Rating extraction with multiple possible paths
        rating = extract_value(product, 
                              ['evaluation.starRating', 'ratings', 'averageStarRate', 'starRating', 'rating', 
                               'star', 'avg_star', 'product_star', 'item_star', 'star_rating', 'avg_rating', 'evaluation'], 
                              'No rating found')
        
        # Handle rating if it's a dictionary
        if isinstance(rating, dict):
            for key in ['starRating', 'averageStar', 'rating', 'value', 'average']:
                if key in rating:
                    rating = rating[key]
                    break
        
        # Link extraction
        product_url = extract_value(product, 
                                   ['productDetailUrl', 'detail_url', 'url', 'productUrl', 'detailUrl', 'item_url', 'product_detail_url'], 
                                   '')
        
        if product_url and not product_url.startswith(('http:', 'https:')):
            product_url = 'https:' + product_url if product_url.startswith('//') else product_url
        
        if not product_url:
            product_url = original_url
        
        # Format price nicely if found
        if price != 'No price found':
            if isinstance(price, (int, float)):
                price = f"US ${price:.2f}"
            elif isinstance(price, str) and price.isdigit():
                price = f"US ${float(price):.2f}"
        
        # Format rating nicely if found
        if rating != 'No rating found':
            if isinstance(rating, (int, float)):
                rating = f"{rating:.1f}/5.0"
            elif isinstance(rating, str) and rating.replace('.', '', 1).isdigit():
                rating = f"{float(rating):.1f}/5.0"
        
        return {
            "Name": str(name),
            "Price": str(price),
            "Rating": str(rating),
            "Link": product_url
        }
        
    except Exception as e:
        print(f"Error processing JSON data: {e}")
        return None

def extract_value(obj, possible_keys, default_value):
    """Extract a value from a nested dictionary using dot notation paths"""
    if not isinstance(obj, dict):
        return default_value
    
    for key_path in possible_keys:
        keys = key_path.split('.')
        current = obj
        valid_path = True
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                valid_path = False
                break
        
        if valid_path:
            return current
    
    return default_value

def parse_html(html_content, original_url):
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Print first product HTML for debugging
    first_product_html = soup.select_one('div[class*="product"]')
    if first_product_html:
        print("First product element found in HTML. Attempting to extract details...")
    
    # More comprehensive set of selectors for product cards
    product_selectors = [
        'div[class*="product-card"]', 
        'div[class*="product-item"]',
        'div.list-item',
        'div[data-product-id]',
        'a[href*="item"]',
        'div.JIIxO',  # Some specific AliExpress classes
        'div._1OUGS',
        'div[class*="list--gallery"]',
        'div[class*="SearchProductFeed"]',
        'div.search-card-item'
    ]
    
    product = None
    for selector in product_selectors:
        products = soup.select(selector)
        if products:
            product = products[0]
            print(f"Found product with selector: {selector}")
            break
    
    if not product:
        print("No products found using HTML parsing.")
        
        # Alternative approach: try to find any element that looks like a product
        potential_products = soup.find_all('a', href=lambda x: x and 'item/' in x)
        if potential_products:
            product = potential_products[0].parent
            print("Found potential product via item link")
    
    if not product:
        return None
    
    # Enhanced selectors for extracting details
    name = find_element(product, [
        'h1', 'h2', 'h3', 
        'div[class*="title"]', 'span[class*="title"]',
        'div.title', '.product-title',
        'a[title]',
        'img[alt]',  # Sometimes the product name is in the image alt
        'div[class*="name"]', 'span[class*="name"]'
    ])
    
    price = find_element(product, [
        'div[class*="price"]', 'span[class*="price"]',
        '.product-price', '.price-current',
        'div.price', 'span.price',
        'strong[class*="price"]',
        'div[class*="Price"]', 'span[class*="Price"]',
        'span.price-current__price',
        'div.price-current__price'
    ])
    
    rating = find_element(product, [
        'span[class*="rating"]', 'span[class*="star"]',
        '.rating-value', '.product-rating',
        'div.rating', 'span.rating',
        'span[class*="Rate"]', 'div[class*="Rate"]',
        'span[class*="Evaluation"]', 
        'span.rating__value',
        'span.product-reviewer-reviews'
    ])
    
    # Get the link with better fallback options
    link = None
    if product.name == 'a':
        link = product.get('href')
    else:
        link_element = product.find('a', href=lambda x: x and ('item' in x or 'product' in x))
        if link_element:
            link = link_element.get('href')
    
    # Format the link properly
    if link and not link.startswith(('http:', 'https:')):
        link = 'https:' + link if link.startswith('//') else 'https://www.aliexpress.com' + link
    
    # Clean and extract text content
    name_text = name.text.strip() if name else None
    if not name_text and name:
        name_text = name.get('title') or name.get('alt')
    if not name_text:
        name_text = "No name found"
    
    price_text = "No price found"
    if price:
        price_text = price.text.strip()
        # Clean price text, removing extra whitespace and newlines
        price_text = re.sub(r'\s+', ' ', price_text)
    
    rating_text = "No rating found"
    if rating:
        rating_text = rating.text.strip()
        # Extract numbers from rating text if possible
        rating_numbers = re.search(r'(\d+\.?\d*)', rating_text)
        if rating_numbers:
            rating_value = float(rating_numbers.group(1))
            rating_text = f"{rating_value:.1f}/5.0"
    
    product_info = {
        "Name": name_text,
        "Price": price_text,
        "Rating": rating_text,
        "Link": link if link else original_url
    }
    
    return product_info

def find_element(parent, selectors):
    for selector in selectors:
        try:
            element = parent.select_one(selector)
            if element:
                return element
        except Exception:
            continue
    return None

if __name__ == "__main__":
    user_input = input("Enter product to search: ")
    result = search_aliexpress(user_input)
    
    if result:
        print("\n--- First Product Found ---")
        for key, value in result.items():
            print(f"{key}: {value}")
    else:
        print("No products found or couldn't retrieve data in English.")
