"""
Product and service data for the AI companion.

This module contains comprehensive information about all offerings on the website:
- Pooja services
- Spiritual products
- Consultation packages
- Service offerings
- Pricing and availability
"""

from typing import Dict, List, Optional
import json


# Comprehensive product and service catalog
PRODUCTS_CATALOG = {
    "pooja_services": {
        "rinmukti": {
            "name": "Rin Mukteshwar Mandir - Rin Mukti Pooja",
            "duration": "2-3 hours",
            "benefits": "Relief from debts and gain financial freedom",
            "includes": "Complete puja with mantras, offerings, and blessings at Rin Mukteshwar Mandir",
            "keywords": ["rin mukti", "debt relief", "financial freedom", "puja", "temple"]
        },
        "sarvabadha": {
            "name": "Sarva Badha Nivaran Pooja",
            "duration": "2-3 hours",
            "benefits": "Remove obstacles and bring peace and prosperity",
            "includes": "Complete puja with mantras, offerings, and blessings",
            "keywords": ["sarvabadha", "obstacles", "peace", "prosperity", "nivaran"]
        },
        "bhaat": {
            "name": "Bhaat Pooja",
            "duration": "2-3 hours",
            "benefits": "Honor ancestors and seek family blessings",
            "includes": "Sacred ritual at Angeshwar Mandir with traditional offerings",
            "keywords": ["bhaat", "ancestors", "family", "blessings", "ritual"]
        },
        "kaalsarp": {
            "name": "Kaal Sarp Pooja",
            "duration": "2-3 hours",
            "benefits": "Overcome Kaal Sarp Dosha and achieve peace, prosperity, and success",
            "includes": "Complete puja at Siddha Nath Mandir with special mantras",
            "keywords": ["kaal sarp", "dosh", "snake", "remedy", "puja"]
        },
        "pitradosh": {
            "name": "Pitra Dosh Pooja",
            "duration": "2-3 hours",
            "benefits": "Honor ancestors, remove Pitra Dosh, and bring peace and prosperity",
            "includes": "Sacred puja at Siddha Nath Mandir with ancestral offerings",
            "keywords": ["pitra dosh", "ancestors", "peace", "prosperity", "remedy"]
        },
        "mahamrityunjaya": {
            "name": "Maha Mrityunjaya Jaap",
            "duration": "1.5-2 hours",
            "benefits": "Protection, healing, and longevity",
            "includes": "Powerful mantra chanting ritual with healing blessings",
            "keywords": ["mahamrityunjaya", "longevity", "health", "healing", "protection"]
        },
        "shivpanchamrat": {
            "name": "Shiv Panchamrat Abhishek",
            "duration": "1-2 hours",
            "benefits": "Blessings and spiritual purification from Lord Mahakal",
            "includes": "Sacred ritual of offering and devotion to Lord Shiva",
            "keywords": ["shiv", "abhishek", "mahakal", "purification", "blessings"]
        },
        "rudrabhishek": {
            "name": "Rudrabhishek",
            "duration": "1-2 hours",
            "benefits": "Blessings, purification, and prosperity from Lord Shiva",
            "includes": "Sacred ritual dedicated to Lord Shiva with traditional offerings",
            "keywords": ["rudrabhishek", "shiva", "purification", "prosperity", "blessings"]
        },
        "pinddaan": {
            "name": "Pind Daan",
            "duration": "2-3 hours",
            "benefits": "Honor ancestors and help their souls attain peace",
            "includes": "Sacred ritual at holy ghats with ancestral offerings",
            "keywords": ["pind daan", "ancestors", "peace", "souls", "ritual"]
        },
        "bagalamukhi": {
            "name": "Maa Bagalamukhi Maha Anushthan",
            "duration": "3-4 hours",
            "benefits": "Protection, victory over enemies, and removal of negativity",
            "includes": "Powerful ritual dedicated to Goddess Bagalamukhi with special mantras",
            "keywords": ["bagalamukhi", "maa", "protection", "enemies", "victory"]
        },
        "angaarakdosh": {
            "name": "Angaarak Dosh Shanti Pujan",
            "duration": "2-3 hours",
            "benefits": "Remove negative effects of Mars (Mangal) and bring peace",
            "includes": "Sacred ritual with specific mantras for Mars pacification",
            "keywords": ["angaarak", "mangal", "mars", "dosh", "shanti"]
        },
        "mangalik": {
            "name": "Mangalik Yog Pujan",
            "duration": "2-3 hours",
            "benefits": "Reduce malefic effects of Mangal Dosha in marriage",
            "includes": "Special puja to pacify Mars for marital harmony",
            "keywords": ["mangalik", "marriage", "mangal", "dosh", "harmony"]
        },
        "mangalgraha": {
            "name": "Mangal Grah Shanti Pooja",
            "duration": "2-3 hours",
            "benefits": "Reduce malefic effects of Mars and bring peace, prosperity, and stability",
            "includes": "Sacred puja at Angareshwar Mandir with Mars-specific rituals",
            "keywords": ["mangal grah", "mars", "shanti", "prosperity", "stability"]
        },
        "sheegravivah": {
            "name": "Sheeghra Vivah Mangalik Pooja",
            "duration": "2-3 hours",
            "benefits": "Early and successful marriage with happiness and harmony",
            "includes": "Special puja for marriage success and marital bliss",
            "keywords": ["sheeghra vivah", "marriage", "success", "happiness", "harmony"]
        },
        "hanumankavach": {
            "name": "1008 Mahakal & Hanuman Raksha Kavach Jaap",
            "duration": "2-3 hours",
            "benefits": "Divine protection, strength, and victory over negativity",
            "includes": "Powerful jaap at Hanuman temples for protection and strength",
            "keywords": ["hanuman", "kavach", "protection", "strength", "victory"]
        },
        "tantrabaadha": {
            "name": "Tantra Baadha Mukti Bhairav Mahasuraksha Yagya",
            "duration": "2-3 hours",
            "benefits": "Protection from black magic, evil forces, and negative energies",
            "includes": "Powerful yagya at Bhairav temples for spiritual protection",
            "keywords": ["tantra", "baadha", "protection", "black magic", "bhairav"]
        },
        "premprapti": {
            "name": "Prem Prapti Aur Sarv Vashikaran Maha Tantrik Bhairav Pooja",
            "duration": "2-3 hours",
            "benefits": "Attract love, strengthen relationships, and gain influence over situations",
            "includes": "Powerful tantric pooja at Bhairav temples for love and relationships",
            "keywords": ["prem prapti", "love", "vashikaran", "relationships", "tantric"]
        }
    },
    
    "spiritual_products": {
        "apamargJadKalawa": {
            "name": "Apamarg Jad Kalawa",
            "price": "₹2,100",
            "description": "Sacred Apamarg root thread blessed with divine mantras for protection and prosperity",
            "keywords": ["apamarg", "kalawa", "thread", "protection", "prosperity"]
        },
        "bagalamukhi-yantra": {
            "name": "Bagalamukhi Yantra",
            "price": "₹2,100",
            "description": "Sacred geometric design representing Maa Bagalamukhi, blessed for victory and protection",
            "keywords": ["bagalamukhi", "yantra", "victory", "protection", "maa"]
        },
        "badha-mukti-yantra": {
            "name": "Badha Mukti Yantra",
            "price": "₹2,100",
            "description": "Sacred geometric design for removing obstacles and negative influences from life",
            "keywords": ["badha mukti", "yantra", "obstacles", "negative", "removal"]
        },
        "laxmi-kuber-yantra": {
            "name": "Laxmi Kuber Yantra",
            "price": "₹2,100",
            "description": "Sacred design combining energies of Goddess Laxmi and Lord Kuber for wealth and prosperity",
            "keywords": ["laxmi", "kuber", "yantra", "wealth", "prosperity"]
        },
        "mahamritunjaya-yantra": {
            "name": "Mahamritunjaya Yantra",
            "price": "₹2,100",
            "description": "Sacred geometric design representing Lord Shiva's divine healing energy for health and protection",
            "keywords": ["mahamritunjaya", "yantra", "shiva", "healing", "health"]
        },
        "vashikaran-yantra": {
            "name": "Vashikaran Yantra",
            "price": "₹2,100",
            "description": "Sacred geometric design for enhancing personal magnetism and positive influence",
            "keywords": ["vashikaran", "yantra", "magnetism", "influence", "attraction"]
        }
    },
    
    "laxmi_potli_packages": {
        "diwali_wealth": {
            "name": "Laxmi Potli - Wealth & Prosperity Package",
            "originalPrice": "₹5,500",
            "specialPrice": "₹2,100",
            "description": "Attract abundance and prosperity with our specially curated Laxmi Potli containing sacred items blessed by Guru Maa",
            "includes": [
                "Energized Laxmi Yantra",
                "Sacred Kamal Gatta (Lotus Seeds)",
                "Pure Khadi Haldi (Raw Turmeric)",
                "Sacred Kaudi (Cowrie Shells)",
                "Blessed Supari (Betel Nut)"
            ],
            "keywords": ["laxmi potli", "wealth", "prosperity", "diwali", "sacred items"]
        },
        "love_relationships": {
            "name": "Love & Relationships Package",
            "originalPrice": "₹5,500",
            "specialPrice": "₹2,100",
            "description": "Enhance attraction, strengthen bonds, and invite divine blessings for harmonious relationships with sacred items blessed by Guru Maa",
            "includes": [
                "Energized Kamdev Yantra",
                "Energized Rati Yantra",
                "Blessed Rose Quartz Crystal",
                "5 Mukhi Rudraksha for Attraction",
                "Beautiful Decorative Potli Bag"
            ],
            "keywords": ["love", "relationships", "attraction", "harmony", "sacred items"]
        },
        "health_wellness": {
            "name": "Health & Wellness Package",
            "originalPrice": "₹5,500",
            "specialPrice": "₹2,100",
            "description": "Promote healing, vitality, and well-being with powerful sacred items blessed by Guru Maa for health and longevity",
            "includes": [
                "Energized Mahamrityunjay Yantra",
                "Energized Dhanvantari Yantra",
                "Blessed Tulsi Mala",
                "7 Mukhi Rudraksha for Health",
                "Beautiful Decorative Potli Bag"
            ],
            "keywords": ["health", "wellness", "healing", "vitality", "longevity"]
        },
        "nazar_protection": {
            "name": "Nazar Protection Package",
            "originalPrice": "₹5,500",
            "specialPrice": "₹2,100",
            "description": "Shield yourself from evil eye and negative energies with powerful protective items blessed by Guru Maa",
            "includes": [
                "Energized Nazar Suraksha Yantra",
                "Energized Kaali Yantra",
                "Blessed Black Thread (Kala Dhaga)",
                "8 Mukhi Rudraksha for Protection",
                "Beautiful Decorative Potli Bag"
            ],
            "keywords": ["nazar", "protection", "evil eye", "negative energies", "safety"]
        }
    },
    
    "consultation_packages": {
        "basic_consultation": {
            "name": "Personal Consultation",
            "price": "₹2,100",
            "duration": "20-30 minutes",
            "includes": "One-on-one call with Guru Maa, personalized guidance, problem analysis",
            "keywords": ["consultation", "personal", "guidance", "call", "guru maa"]
        }
    }
}

def find_products_by_text(text: str) -> List[Dict]:
    """
    Find relevant products/services based on user text.
    
    Args:
        text: User's message text
        
    Returns:
        List of matching products/services with details
    """
    text_lower = text.lower()
    matches = []
    
    # Search through all categories
    for category, items in PRODUCTS_CATALOG.items():
        for item_id, item_data in items.items():
            # Check if any keywords match
            keywords = item_data.get("keywords", [])
            if any(keyword in text_lower for keyword in keywords):
                match = {
                    "category": category,
                    "id": item_id,
                    **item_data
                }
                matches.append(match)
    
    return matches


def format_product_context(products: List[Dict]) -> str:
    """
    Format product information for injection into conversation context.
    
    Args:
        products: List of matched products
        
    Returns:
        Formatted string with product information
    """
    if not products:
        return ""
    
    context = "**Relevant Products/Services:**\n\n"
    
    for product in products:
        # Handle price field that might not exist for all products
        price_info = ""
        if 'price' in product:
            price_info = f" - {product['price']}"
        elif 'originalPrice' in product and 'specialPrice' in product:
            price_info = f" - {product['specialPrice']} (was {product['originalPrice']})"
        
        context += f"**{product['name']}**{price_info}\n"
        
        if 'duration' in product:
            context += f"Duration: {product['duration']}\n"
        
        if 'benefits' in product:
            context += f"Benefits: {product['benefits']}\n"
        elif 'description' in product:
            context += f"Description: {product['description']}\n"
        
        if 'includes' in product:
            context += f"Includes: {product['includes']}\n"
        
        context += "\n"
    
    return context


def get_all_products_summary() -> str:
    """
    Get a summary of all available products and services.
    
    Returns:
        Formatted string with all offerings
    """
    summary = "**Complete Product & Service Catalog:**\n\n"
    
    # Pooja Services
    summary += "**Pooja Services:**\n"
    for item in PRODUCTS_CATALOG["pooja_services"].values():
        summary += f"• {item['name']} - {item['price']}\n"
    summary += "\n"
    
    # Spiritual Products
    summary += "**Spiritual Products:**\n"
    for item in PRODUCTS_CATALOG["spiritual_products"].values():
        summary += f"• {item['name']} - {item['price']}\n"
    summary += "\n"
    
    # Consultation Packages
    summary += "**Consultation Packages:**\n"
    for item in PRODUCTS_CATALOG["consultation_packages"].values():
        summary += f"• {item['name']} - {item['price']}\n"
    summary += "\n"
    
    return summary


def get_relevant_products_with_ai(user_text: str) -> str:
    """
    Use AI to extract relevant product context from the full catalog based on user input.
    
    Args:
        user_text: The user's message or conversation context
        
    Returns:
        Formatted string with relevant product information for the conversation
    """
    # Create a comprehensive prompt for the AI to analyze
    ai_prompt = f"""
You are an AI assistant helping to provide relevant product and service information from a comprehensive catalog.

**USER INPUT TO ANALYZE:**
{user_text}

**FULL PRODUCT CATALOG:**
{json.dumps(PRODUCTS_CATALOG, indent=2, ensure_ascii=False)}

**TASK:**
Based on the user input above, extract and format ONLY the most relevant products/services from the catalog that would be helpful for the user's inquiry.

**INSTRUCTIONS:**
1. Analyze the user's text for any mentions of:
   - Specific product names (pooja services, spiritual products, packages)
   - Problems they're facing (debt, health, relationships, protection, etc.)
   - Intentions (marriage, prosperity, healing, etc.)
   - General spiritual/religious inquiries

2. From the catalog, select products that match their needs, problems, or interests

3. Format your response as a helpful context that can be injected into a conversation

4. Include:
   - Product name
   - Price (if available)
   - Key benefits
   - Brief description of what it includes
   - Duration (for services)

5. If no specific products match, return an empty string

6. Keep the response concise but informative
7. Use natural language that would be helpful in a conversation

**RESPONSE FORMAT:**
If relevant products are found, format like this:

**Relevant Products/Services:**

**Product Name** - Price
Benefits: [key benefits]
Description: [what it includes]
Duration: [if applicable]

[Repeat for other relevant products]

If no relevant products are found, return an empty string.
"""

    try:
        # Import here to avoid circular dependency
        from ai_companion.graph.utils.helpers import get_chat_model
        
        # Get the chat model
        model = get_chat_model()
        
        # Get AI response
        response = model.invoke(ai_prompt)
        
        # Extract the content from the response
        if hasattr(response, 'content'):
            ai_response = response.content
        else:
            ai_response = str(response)
        
        # Clean up the response - remove any extra formatting
        ai_response = ai_response.strip()
        
        # If the AI says no relevant products or returns empty, return empty string
        if not ai_response or "no relevant products" in ai_response.lower() or "empty string" in ai_response.lower():
            return ""
            
        return ai_response
        
    except Exception as e:
        # Fallback to keyword-based approach if AI fails
        print(f"AI product extraction failed: {e}, falling back to keyword matching")
        detected_products = find_products_by_text(user_text)
        return format_product_context(detected_products)
