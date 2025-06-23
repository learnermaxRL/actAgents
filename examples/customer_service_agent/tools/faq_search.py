"""FAQ search tool for customer service agent."""

from typing import Dict, Any, List
from utils.logger import get_logger

logger = get_logger("faq_search")

# Sample FAQ database for demo purposes
# In production, this would be a real database or knowledge base
FAQ_DATABASE = {
    "billing": [
        {
            "question": "How do I update my payment method?",
            "answer": "You can update your payment method by going to Account Settings > Billing > Payment Methods. Click 'Add New Payment Method' and follow the prompts to add your new card or bank account.",
            "category": "billing",
            "tags": ["payment", "billing", "account"]
        },
        {
            "question": "Why was I charged twice?",
            "answer": "If you see a duplicate charge, it might be a pending authorization that will drop off within 3-5 business days. If the charge remains after 5 days, please contact our billing support team with your order number.",
            "category": "billing",
            "tags": ["charge", "duplicate", "billing"]
        },
        {
            "question": "How do I get a refund?",
            "answer": "To request a refund, please contact our support team with your order number and reason for the refund. Refunds are typically processed within 5-10 business days and will be credited back to your original payment method.",
            "category": "billing",
            "tags": ["refund", "billing", "money"]
        }
    ],
    "technical": [
        {
            "question": "How do I reset my password?",
            "answer": "To reset your password, go to the login page and click 'Forgot Password'. Enter your email address and follow the link sent to your email to create a new password.",
            "category": "technical",
            "tags": ["password", "login", "account"]
        },
        {
            "question": "The app is not working on my phone",
            "answer": "Try these steps: 1) Close and reopen the app, 2) Check if you have the latest version, 3) Clear the app cache, 4) Restart your phone. If the issue persists, please contact technical support.",
            "category": "technical",
            "tags": ["app", "mobile", "technical"]
        },
        {
            "question": "How do I enable two-factor authentication?",
            "answer": "Go to Account Settings > Security > Two-Factor Authentication. Choose between SMS or authenticator app, then follow the setup instructions to complete the process.",
            "category": "technical",
            "tags": ["security", "2fa", "authentication"]
        }
    ],
    "product": [
        {
            "question": "What's your return policy?",
            "answer": "We offer a 30-day return policy for most items. Items must be unused and in original packaging. Some items may have different return policies - check the product page for specific details.",
            "category": "product",
            "tags": ["return", "policy", "refund"]
        },
        {
            "question": "Do you ship internationally?",
            "answer": "Yes, we ship to most countries. International shipping typically takes 7-14 business days. Shipping costs and delivery times vary by location - you'll see the exact cost at checkout.",
            "category": "product",
            "tags": ["shipping", "international", "delivery"]
        },
        {
            "question": "How do I track my order?",
            "answer": "You can track your order by logging into your account and going to Order History, or by using the tracking number sent to your email. Click on the order to see detailed tracking information.",
            "category": "product",
            "tags": ["tracking", "order", "delivery"]
        }
    ],
    "account": [
        {
            "question": "How do I change my email address?",
            "answer": "Go to Account Settings > Profile > Email Address. Enter your new email and verify it through the confirmation link sent to your new email address.",
            "category": "account",
            "tags": ["email", "profile", "account"]
        },
        {
            "question": "Can I have multiple accounts?",
            "answer": "Each email address can only be associated with one account. If you need to manage multiple businesses, you can create separate accounts with different email addresses.",
            "category": "account",
            "tags": ["multiple", "accounts", "business"]
        }
    ],
    "order": [
        {
            "question": "How long does shipping take?",
            "answer": "Standard shipping takes 3-5 business days. Express shipping (1-2 business days) is available for an additional fee. International orders take 7-14 business days.",
            "category": "order",
            "tags": ["shipping", "delivery", "timeline"]
        },
        {
            "question": "Can I cancel my order?",
            "answer": "Orders can be cancelled within 1 hour of placement if they haven't been processed yet. Go to Order History and click 'Cancel Order' if the option is available.",
            "category": "order",
            "tags": ["cancel", "order", "timeline"]
        }
    ],
    "refund": [
        {
            "question": "How long do refunds take?",
            "answer": "Refunds are typically processed within 5-10 business days. The time to appear in your account depends on your bank or credit card provider, which can take an additional 3-5 business days.",
            "category": "refund",
            "tags": ["refund", "timeline", "money"]
        }
    ]
}

async def search_faq(**kwargs) -> Dict[str, Any]:
    """
    Search the FAQ database for answers to customer questions.
    
    Args:
        **kwargs: Search parameters including query, category, max_results, etc.
    
    Returns:
        Dict containing FAQ search results
    """
    try:
        query = kwargs.get("query", "").lower()
        category = kwargs.get("category", "all")
        max_results = kwargs.get("max_results", 3)
        include_related = kwargs.get("include_related", True)
        
        logger.info(f"Searching FAQ for: '{query}' in category: {category}")
        
        # Determine which categories to search
        if category == "all":
            categories_to_search = list(FAQ_DATABASE.keys())
        else:
            categories_to_search = [category] if category in FAQ_DATABASE else []
        
        # Search through relevant categories
        results = []
        for cat in categories_to_search:
            if cat in FAQ_DATABASE:
                for faq in FAQ_DATABASE[cat]:
                    # Simple keyword matching (in production, use proper search engine)
                    question_lower = faq["question"].lower()
                    answer_lower = faq["answer"].lower()
                    tags_lower = [tag.lower() for tag in faq.get("tags", [])]
                    
                    # Check if query matches question, answer, or tags
                    if (query in question_lower or 
                        query in answer_lower or 
                        any(query in tag for tag in tags_lower)):
                        
                        results.append({
                            "question": faq["question"],
                            "answer": faq["answer"],
                            "category": faq["category"],
                            "tags": faq.get("tags", []),
                            "relevance_score": _calculate_relevance(query, faq)
                        })
        
        # Sort by relevance and limit results
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:max_results]
        
        if results:
            return {
                "success": True,
                "query": query,
                "results_count": len(results),
                "results": results,
                "message": f"Found {len(results)} relevant FAQ entries for your question."
            }
        else:
            return {
                "success": True,
                "query": query,
                "results_count": 0,
                "results": [],
                "message": "I couldn't find a specific FAQ answer for your question. Would you like me to create a support ticket to get you personalized help?"
            }
        
    except Exception as e:
        logger.error(f"FAQ search failed: {e}")
        return {
            "success": False,
            "error": f"FAQ search failed: {str(e)}",
            "message": "Sorry, I couldn't search the FAQ database at this time. Please try again or contact support directly."
        }

def _calculate_relevance(query: str, faq: Dict[str, Any]) -> float:
    """
    Calculate relevance score for FAQ matching.
    
    Args:
        query: Search query
        faq: FAQ entry
    
    Returns:
        Relevance score (higher is better)
    """
    score = 0.0
    
    # Exact question match gets highest score
    if query in faq["question"].lower():
        score += 10.0
    
    # Question contains query words
    query_words = query.split()
    question_words = faq["question"].lower().split()
    for word in query_words:
        if word in question_words:
            score += 2.0
    
    # Answer contains query
    if query in faq["answer"].lower():
        score += 5.0
    
    # Tag matches
    tags_lower = [tag.lower() for tag in faq.get("tags", [])]
    for word in query_words:
        if word in tags_lower:
            score += 1.0
    
    return score 