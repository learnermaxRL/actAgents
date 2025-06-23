create_ticket_tool_schema = {
    "type": "function",
    "function": {
        "name": "create_ticket",
        "description": "Create a new support ticket for customer issues. Use this when a customer needs help that requires tracking or escalation.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Full name of the customer"
                },
                "customer_email": {
                    "type": "string",
                    "description": "Email address of the customer"
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["billing", "technical", "product", "account", "order", "refund", "general"],
                    "description": "Category of the issue"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Priority level of the ticket"
                },
                "subject": {
                    "type": "string",
                    "description": "Brief subject line describing the issue"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue and what the customer needs help with"
                },
                "order_number": {
                    "type": "string",
                    "description": "Order number if the issue is related to a purchase (optional)"
                },
                "product_name": {
                    "type": "string",
                    "description": "Product name if the issue is related to a specific product (optional)"
                }
            },
            "required": ["customer_name", "customer_email", "issue_type", "priority", "subject", "description"]
        }
    }
}

update_ticket_tool_schema = {
    "type": "function",
    "function": {
        "name": "update_ticket",
        "description": "Update an existing support ticket with new information or status changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Unique identifier of the ticket to update"
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "waiting_for_customer", "resolved", "closed"],
                    "description": "New status for the ticket"
                },
                "update_message": {
                    "type": "string",
                    "description": "Message to add to the ticket (e.g., resolution steps, follow-up questions)"
                },
                "assigned_to": {
                    "type": "string",
                    "description": "Name of the support agent assigned to the ticket (optional)"
                },
                "resolution_notes": {
                    "type": "string",
                    "description": "Detailed notes about how the issue was resolved (optional)"
                }
            },
            "required": ["ticket_id", "status", "update_message"]
        }
    }
} 