search_faq_tool_schema = {
    "type": "function",
    "function": {
        "name": "search_faq",
        "description": "Search the FAQ database for answers to common customer questions. Use this to provide quick, accurate information to customers.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The customer's question or search terms"
                },
                "category": {
                    "type": "string",
                    "enum": ["billing", "technical", "product", "account", "order", "refund", "general", "all"],
                    "description": "FAQ category to search in (use 'all' for general search)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of FAQ results to return (default: 3)",
                    "default": 3
                },
                "include_related": {
                    "type": "boolean",
                    "description": "Whether to include related questions in the search results",
                    "default": True
                }
            },
            "required": ["query"]
        }
    }
} 