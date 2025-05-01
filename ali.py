import requests
from bs4 import BeautifulSoup
import json
import re
import time
import random

def search_aliexpress(product_name):
    """Search AliExpress for a product and return the first result"""
    # Try both search URL formats that AliExpress might use
    search_urls = [
        f"https://www.aliexpress.com/w/wholesale-{product_name.replace(' ', '-')}.html",
        f"https://www.aliexpress.com/wholesale?SearchText={product_name.replace(' ', '+')}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Cookie": "aep_usuc_f=site=glo&c_tp=USD&region=US&b_locale=en_US"
    }
    
    # Try each search URL format
    for search_url in search_urls:
        try:
            time.sleep(random.uniform(1, 2))
            response = requests.get(search_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                continue
            
            # First try to extract data from JSON
            json_data = extract_json_data(response.text)
            if json_data:
                result = process_json_data(json_data, search_url)
                if result and result["Name"] != "No name found":
                    return result
            
            # Fall back to HTML parsing
            result = parse_html(response.text, search_url)
            if result and result["Name"] != "No name found":
                return result
                
        except Exception as e:
            print(f"Error with URL {search_url}: {e}")
    
    # If both URLs fail, return None
    return None

def extract_json_data(html_content):
    """Extract product JSON data from the page HTML"""
    # Check for different JSON data patterns that AliExpress might use
    json_patterns = [
        r'window\.__INIT_DATA__\s*=\s*({.*?});',
        r'window\.__data\s*=\s*({.*?});',
        r'window\.runParams\s*=\s*({.*?});',
        r'"items"\s*:\s*(\[.*?\])',
        r'"productList"\s*:\s*(\[.*?\])',
        r'window\._init_data_\s*=\s*({.*?});\s*</script>',
        r'data: ({.*?}),\s*[,;]'
    ]
    
    for pattern in json_patterns:
        matches = re.finditer(pattern, html_content, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match.group(1))
                # Quick check if this JSON contains product data
                if contains_product_data(data):
                    return data
            except json.JSONDecodeError:
                continue
    
    # Look for data-spm-anchor-id script tags which often contain product data
    soup = BeautifulSoup(html_content, "html.parser")
    script_tags = soup.find_all('script', attrs={"data-spm-anchor-id": True})
    
    for script in script_tags:
        if script.string:
            try:
                # Try to find JSON objects within the script
                json_matches = re.finditer(r'{[\s\S]*?"products"[\s\S]*?}', script.string)
                for match in json_matches:
                    try:
                        # Clean up the JSON string to fix common issues
                        json_str = match.group(0)
                        json_str = re.sub(r',\s*}', '}', json_str)
                        json_str = re.sub(r',\s*]', ']', json_str)
                        data = json.loads(json_str)
                        if contains_product_data(data):
                            return data
                    except json.JSONDecodeError:
                        continue
            except Exception:
                continue
    
    return None

def contains_product_data(data):
    """Check if the JSON data contains product information"""
    if not isinstance(data, (dict, list)):
        return False
    
    # Check if it's a list of products
    if isinstance(data, list) and len(data) > 0:
        first_item = data[0]
        return isinstance(first_item, dict) and any(k in first_item for k in ['title', 'name', 'productTitle', 'price'])
    
    # Check common product data keys
    product_indicators = ['products', 'items', 'resultList', 'productList', 'searchResult', 'mods']
    if isinstance(data, dict):
        # Check if any product indicator keys exist
        if any(key in data for key in product_indicators):
            return True
        
        # Check for nested product data in first-level keys
        for key, value in data.items():
            if isinstance(value, dict) and any(k in value for k in product_indicators):
                return True
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and any(k in value[0] for k in ['title', 'name', 'price']):
                return True
    
    return False

def process_json_data(data, original_url):
    """Process extracted JSON data to get product information"""
    try:
        # Find products list in the JSON structure
        products = None
        
        # Check common paths where products might be located
        possible_paths = [
            ['pageModule', 'resultList'],
            ['items'],
            ['products'],
            ['data', 'products'],
            ['mods', 'itemList', 'content'],
            ['data', 'root', 'fields', 'productsFeed', 'products'],
            ['data', 'root', 'fields', 'items']
        ]
        
        # Try to find products in the data structure
        if isinstance(data, list) and len(data) > 0:
            products = data
        elif isinstance(data, dict):
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
                    break
        
        if not products:
            return None
        
        # Get the first product
        product = products[0]
        
        # Extract product details - expanded keyword list
        name = extract_value(product, [
            'title', 'name', 'productTitle', 'subject', 'item_title', 
            'product_title', 'displayTitle', 'productName'
        ], 'No name found')
        
        # Extended price paths to check
        price = extract_value(product, [
            'price.formattedPrice', 'price', 'minPrice', 'salePrice',
            'price.minAmount.value', 'price.amount.value', 'priceInfo.formatedActivityPrice',
            'priceModule.formatedPrice', 'priceModule.minPrice', 'priceInfo.formatedPrice',
            'discount_price', 'sale_price', 'discountPrice', 'sku_price'
        ], 'No price found')
        
        # Handle price if it's a dictionary with more possible keys
        if isinstance(price, dict):
            for key in ['formattedPrice', 'minPrice', 'value', 'text', 'amount', 'formatedPrice']:
                if key in price:
                    price = price[key]
                    break
        
        # Extended rating paths to check
        rating = extract_value(product, [
            'evaluation.starRating', 'ratings', 'starRating', 'rating', 
            'evaluation.starRating.averageStar', 'feedbackRating', 'averageStarRate',
            'reviews.averageStar', 'reviewModule.averageStar', 'averageStar'
        ], 'No rating found')
        
        # Handle rating if it's a dictionary with more possible keys
        if isinstance(rating, dict):
            for key in ['starRating', 'rating', 'value', 'averageStar', 'average']:
                if key in rating:
                    rating = rating[key]
                    break
        
        # Get product URL
        product_url = extract_value(product, 
                                   ['productDetailUrl', 'detail_url', 'url', 'productUrl'], 
                                   '')
        
        if product_url and not product_url.startswith(('http:', 'https:')):
            product_url = 'https:' + product_url if product_url.startswith('//') else product_url
        
        if not product_url:
            product_url = original_url
        
        # Format price if it's a number
        if price != 'No price found' and isinstance(price, (int, float)):
            price = f"US ${price:.2f}"
        
        # Format rating if it's a number
        if rating != 'No rating found' and isinstance(rating, (int, float)):
            rating = f"{rating:.1f}/5.0"
        
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
    """Parse product information from HTML when JSON extraction fails"""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Expanded selectors for product cards
    product_selectors = [
        'div[class*="product-card"]', 
        'div[class*="product-item"]',
        'div.list-item',
        'div[data-product-id]',
        'a[href*="item"]',
        'div.JIIxO',  # AliExpress specific classes
        'div._1OUGS',
        'div[class*="list--gallery"]',
        'div[class*="SearchProductFeed"]',
        'div.search-card-item',
        'li[class*="list-item"]'
    ]
    
    # Find a product element
    product = None
    for selector in product_selectors:
        products = soup.select(selector)
        if products:
            product = products[0]
            break
    
    if not product:
        # Try to find by link as fallback
        potential_products = soup.find_all('a', href=lambda x: x and 'item/' in x)
        if potential_products:
            product = potential_products[0].parent
    
    if not product:
        # As a last resort, try to find product containers with pricing info
        price_elements = soup.select('span[class*="price"], div[class*="price"]')
        if price_elements:
            # Find closest parent that could be a product container
            for price_el in price_elements:
                potential_product = price_el.find_parent(['div', 'li'], class_=lambda x: x and ('item' in x or 'product' in x))
                if potential_product:
                    product = potential_product
                    break
    
    if not product:
        return None
    
    # Extract product details with expanded selectors
    name = find_element(product, [
        'h1', 'h2', 'h3', 
        'div[class*="title"]', 'span[class*="title"]',
        'a[title]', 'img[alt]',
        'div[class*="name"]', 'span[class*="name"]',
        '.product-name', '.item-title',
        '[class*="ProductTitle"]'
    ])
    
    price = find_element(product, [
        'div[class*="price"]', 'span[class*="price"]',
        '.product-price', '.price-current',
        'div.price', 'span.price',
        'strong[class*="price"]',
        'div[class*="Price"]', 'span[class*="Price"]',
        'span.price-current__price',
        'div[class*="lj_kr"]',
        '.uniform-banner-box-price',
        'div[class*="PriceModule"]'
    ])
    
    rating = find_element(product, [
        'span[class*="rating"]', 'span[class*="star"]',
        '.rating-value', '.product-rating',
        'div.rating', 'span.rating',
        'span[class*="Rate"]', 'div[class*="Rate"]',
        'span[class*="Evaluation"]', 
        'span.rating__value',
        'span.product-reviewer-reviews',
        'div[class*="lj_kx"]',
        'span[class*="score"]', 'div[class*="score"]'
    ])
    
    # Get the link
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
    
    # Extract text content
    name_text = name.text.strip() if name else None
    if not name_text and name:
        name_text = name.get('title') or name.get('alt')
    if not name_text:
        name_text = "No name found"
    
    price_text = "No price found"
    if price:
        price_text = price.text.strip()
        # Clean price text
        price_text = re.sub(r'\s+', ' ', price_text)
        # Check if price has any digits
        if not re.search(r'\d', price_text):
            # Try to find price attribute or content
            price_val = price.get('data-price') or price.get('content')
            if price_val and re.search(r'\d', str(price_val)):
                price_text = f"US ${price_val}"
    
    rating_text = "No rating found"
    if rating:
        # Look for style-based star rating (common on AliExpress)
        rating_style = rating.get('style')
        if rating_style and 'width' in rating_style:
            width_match = re.search(r'width:\s*(\d+(?:\.\d+)?)%', rating_style)
            if width_match:
                width_percent = float(width_match.group(1))
                rating_value = (width_percent / 20)  # Convert percent to 5-star scale
                rating_text = f"{rating_value:.1f}/5.0"
        else:
            rating_text = rating.text.strip()
            # Extract numbers from rating text if possible
            rating_numbers = re.search(r'(\d+\.?\d*)', rating_text)
            if rating_numbers:
                rating_value = float(rating_numbers.group(1))
                if rating_value <= 5:  # Assume 5-star scale
                    rating_text = f"{rating_value:.1f}/5.0"
                else:  # Could be a percentage
                    rating_value = rating_value / 20
                    rating_text = f"{rating_value:.1f}/5.0"
    
    return {
        "Name": name_text,
        "Price": price_text,
        "Rating": rating_text,
        "Link": link if link else original_url
    }

def find_element(parent, selectors):
    """Find an element using multiple selectors"""
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
        print("No products found or couldn't retrieve data.")
