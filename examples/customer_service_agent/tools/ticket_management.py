"""Ticket management tools for customer service agent."""

import uuid
from typing import Dict, Any, List
from datetime import datetime
from utils.logger import get_logger

logger = get_logger("ticket_management")

# In-memory storage for demo purposes
# In production, this would be a database
ticket_database = {}

async def create_ticket(**kwargs) -> Dict[str, Any]:
    """
    Create a new support ticket.
    
    Args:
        **kwargs: Ticket parameters including customer_name, customer_email, issue_type, etc.
    
    Returns:
        Dict containing ticket information and confirmation
    """
    try:
        # Generate unique ticket ID
        ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Create ticket record
        ticket = {
            "ticket_id": ticket_id,
            "created_at": datetime.now().isoformat(),
            "status": "open",
            "customer_name": kwargs.get("customer_name"),
            "customer_email": kwargs.get("customer_email"),
            "issue_type": kwargs.get("issue_type"),
            "priority": kwargs.get("priority"),
            "subject": kwargs.get("subject"),
            "description": kwargs.get("description"),
            "order_number": kwargs.get("order_number"),
            "product_name": kwargs.get("product_name"),
            "updates": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Ticket created: {kwargs.get('description')}",
                    "status": "open"
                }
            ]
        }
        
        # Store in database
        ticket_database[ticket_id] = ticket
        
        logger.info(f"Created ticket {ticket_id} for {kwargs.get('customer_name')}")
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Support ticket {ticket_id} has been created successfully.",
            "ticket_details": {
                "id": ticket_id,
                "status": "open",
                "priority": kwargs.get("priority"),
                "issue_type": kwargs.get("issue_type"),
                "subject": kwargs.get("subject"),
                "estimated_response_time": "2-4 hours" if kwargs.get("priority") in ["high", "urgent"] else "24 hours"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create ticket: {e}")
        return {
            "success": False,
            "error": f"Failed to create ticket: {str(e)}",
            "message": "Sorry, I couldn't create the ticket at this time. Please try again or contact support directly."
        }

async def update_ticket(**kwargs) -> Dict[str, Any]:
    """
    Update an existing support ticket.
    
    Args:
        **kwargs: Update parameters including ticket_id, status, update_message, etc.
    
    Returns:
        Dict containing update confirmation
    """
    try:
        ticket_id = kwargs.get("ticket_id")
        
        if ticket_id not in ticket_database:
            return {
                "success": False,
                "error": "Ticket not found",
                "message": f"Ticket {ticket_id} was not found in our system."
            }
        
        ticket = ticket_database[ticket_id]
        
        # Update ticket
        new_status = kwargs.get("status")
        update_message = kwargs.get("update_message")
        
        ticket["status"] = new_status
        ticket["updates"].append({
            "timestamp": datetime.now().isoformat(),
            "message": update_message,
            "status": new_status,
            "assigned_to": kwargs.get("assigned_to"),
            "resolution_notes": kwargs.get("resolution_notes")
        })
        
        # Update database
        ticket_database[ticket_id] = ticket
        
        logger.info(f"Updated ticket {ticket_id} to status: {new_status}")
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Ticket {ticket_id} has been updated successfully.",
            "updated_details": {
                "id": ticket_id,
                "new_status": new_status,
                "update_message": update_message,
                "last_updated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to update ticket {kwargs.get('ticket_id')}: {e}")
        return {
            "success": False,
            "error": f"Failed to update ticket: {str(e)}",
            "message": "Sorry, I couldn't update the ticket at this time. Please try again."
        } 