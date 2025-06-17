"""Browse AI scraper for Portuguese legal documents."""

import requests
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import json

logger = logging.getLogger(__name__)


class BrowseAIScraper:
    """Scraper using Browse AI API for Portuguese legal documents."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BROWSE_AI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Browse AI API key is required. Set BROWSE_AI_API_KEY environment variable."
            )

        self.base_url = "https://api.browse.ai/v2"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def get_robots(self) -> List[Dict[str, Any]]:
        """Get all available robots in your Browse AI account."""
        try:
            response = self.session.get(f"{self.base_url}/robots")
            response.raise_for_status()

            data = response.json()
            # Browse AI API returns robots in 'robots.items', not 'result.robots'
            robots = data.get("robots", {}).get("items", [])

            logger.info(f"Found {len(robots)} robots in account")
            return robots

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching robots: {e}")
            if hasattr(e, "response"):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error fetching robots: {e}")
            return []

    def run_robot(
        self, robot_id: str, input_parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Run a Browse AI robot and return the task ID.

        Args:
            robot_id: The ID of the robot to run
            input_parameters: Optional parameters for the robot

        Returns:
            Task ID if successful, None otherwise
        """
        try:
            payload = {}
            if input_parameters:
                payload["inputParameters"] = input_parameters

            response = self.session.post(
                f"{self.base_url}/robots/{robot_id}/tasks", json=payload
            )
            response.raise_for_status()

            data = response.json()
            # Browse AI API may return task in different structure
            task_id = data.get("result", {}).get("robotTask", {}).get("id") or data.get(
                "robotTask", {}
            ).get("id")

            if task_id:
                logger.info(f"Started robot {robot_id}, task ID: {task_id}")
                return task_id
            else:
                logger.error(f"No task ID returned for robot {robot_id}")
                return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                try:
                    error_data = e.response.json()
                    if error_data.get("messageCode") == "credits_limit_reached":
                        logger.error(
                            f"Browse AI credits limit reached. Please check your Browse AI account billing."
                        )
                    else:
                        logger.error(
                            f"Access forbidden for robot {robot_id}: {error_data}"
                        )
                except:
                    logger.error(f"Access forbidden for robot {robot_id}")
            else:
                logger.error(f"HTTP error running robot {robot_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error running robot {robot_id}: {e}")
            return None

    def get_task_status(self, robot_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status and results of a robot task.

        Args:
            robot_id: The robot ID
            task_id: The task ID

        Returns:
            Task data with status and results
        """
        try:
            response = self.session.get(
                f"{self.base_url}/robots/{robot_id}/tasks/{task_id}"
            )
            response.raise_for_status()

            data = response.json()
            # Browse AI API may return task in different structure
            task_data = data.get("result", {}).get("robotTask", {}) or data.get(
                "robotTask", {}
            )

            return task_data

        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return None

    def wait_for_task_completion(
        self, robot_id: str, task_id: str, timeout: int = 300, poll_interval: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a task to complete and return the results.

        Args:
            robot_id: The robot ID
            task_id: The task ID
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds

        Returns:
            Task results if successful, None otherwise
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            task_data = self.get_task_status(robot_id, task_id)

            if not task_data:
                logger.error(f"Failed to get task status for {task_id}")
                return None

            status = task_data.get("status")
            logger.info(f"Task {task_id} status: {status}")

            if status == "successful":
                return task_data
            elif status == "failed":
                logger.error(f"Task {task_id} failed: {task_data.get('error')}")
                return None
            elif status in ["running", "pending"]:
                time.sleep(poll_interval)
            else:
                logger.warning(f"Unknown task status: {status}")
                time.sleep(poll_interval)

        logger.error(f"Task {task_id} timed out after {timeout} seconds")
        return None

    def scrape_recent_documents(
        self,
        robot_id: str,
        days_back: int = 7,
        max_documents: int = 100,
        input_parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scrape recent documents using a Browse AI robot.

        Args:
            robot_id: The Browse AI robot ID for scraping Diário da República
            days_back: Number of days to look back (may be used in input_parameters)
            max_documents: Maximum number of documents to return
            input_parameters: Additional parameters for the robot

        Returns:
            List of scraped document dictionaries
        """
        logger.info(f"Starting document scrape with robot {robot_id}")

        # Prepare input parameters
        if input_parameters is None:
            input_parameters = {}

        # Add date range if supported by the robot
        input_parameters.update(
            {"days_back": days_back, "max_documents": max_documents}
        )

        # Run the robot
        task_id = self.run_robot(robot_id, input_parameters)
        if not task_id:
            logger.error("Failed to start robot task")
            return []

        # Wait for completion
        task_data = self.wait_for_task_completion(robot_id, task_id)
        if not task_data:
            logger.error("Task did not complete successfully")
            return []

        # Extract documents from results
        documents = self._extract_documents_from_task(task_data)

        logger.info(f"Successfully scraped {len(documents)} documents")
        return documents[:max_documents]

    def _extract_documents_from_task(
        self, task_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract document data from Browse AI task results.

        Args:
            task_data: The completed task data from Browse AI

        Returns:
            List of document dictionaries
        """
        documents = []

        try:
            # Browse AI typically returns data in capturedLists
            captured_lists = task_data.get("capturedLists", {})

            # Look for document lists (adjust key names based on your robot configuration)
            for list_name, list_data in captured_lists.items():
                if isinstance(list_data, list):
                    for item in list_data:
                        doc = self._parse_browse_ai_document(item)
                        if doc:
                            documents.append(doc)

        except Exception as e:
            logger.error(f"Error extracting documents from task results: {e}")

        return documents

    def _parse_browse_ai_document(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a document item from Browse AI results.

        Args:
            item: Document item from Browse AI results

        Returns:
            Standardized document dictionary
        """
        try:
            # Map Browse AI fields to our document structure
            # Adjust field names based on your robot configuration
            document = {
                "source": "browse_ai",
                "title": item.get("title", ""),
                "document_number": item.get("document_number", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "document_type": self._extract_document_type(
                    item.get("title", ""), item.get("document_number", "")
                ),
                "publication_date": item.get("publication_date", ""),
                "scraped_at": datetime.now().isoformat(),
                "full_text": item.get("full_text", ""),
                "metadata": {
                    "source_url": item.get("source_url", ""),
                    "browse_ai_task": True,
                    "raw_data": item,  # Keep original data for debugging
                },
            }

            # Calculate text length if full text is available
            if document["full_text"]:
                document["text_length"] = len(document["full_text"])

            return document

        except Exception as e:
            logger.error(f"Error parsing Browse AI document: {e}")
            return None

    def _extract_document_type(self, title: str, number: str) -> str:
        """Extract document type from title and number."""
        # Reuse the same logic from the original scraper
        import re

        type_patterns = {
            "lei": r"Lei n\.?º?\s*\d+",
            "decreto_lei": r"Decreto-Lei n\.?º?\s*\d+",
            "decreto": r"Decreto n\.?º?\s*\d+",
            "portaria": r"Portaria n\.?º?\s*\d+",
            "despacho": r"Despacho n\.?º?\s*\d+",
            "resolucao": r"Resolução.*n\.?º?\s*\d+",
            "regulamento": r"Regulamento n\.?º?\s*\d+",
            "aviso": r"Aviso n\.?º?\s*\d+",
            "deliberacao": r"Deliberação n\.?º?\s*\d+",
        }

        combined_text = f"{title} {number}".lower()

        for doc_type, pattern in type_patterns.items():
            if re.search(pattern, combined_text, re.IGNORECASE):
                return doc_type

        return "other"

    def get_robot_by_name(self, robot_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a robot by its name.

        Args:
            robot_name: Name of the robot to find

        Returns:
            Robot data if found, None otherwise
        """
        robots = self.get_robots()

        for robot in robots:
            if robot.get("name", "").lower() == robot_name.lower():
                return robot

        logger.warning(f"Robot '{robot_name}' not found")
        return None

    def list_robot_tasks(self, robot_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List recent tasks for a robot.

        Args:
            robot_id: The robot ID
            limit: Maximum number of tasks to return

        Returns:
            List of task data
        """
        try:
            params = {"limit": limit}
            response = self.session.get(
                f"{self.base_url}/robots/{robot_id}/tasks", params=params
            )
            response.raise_for_status()

            data = response.json()
            # Browse AI API may return tasks in different structure
            tasks = data.get("result", {}).get("robotTasks", []) or data.get(
                "robotTasks", {}
            ).get("items", [])

            logger.info(f"Found {len(tasks)} recent tasks for robot {robot_id}")
            return tasks

        except Exception as e:
            logger.error(f"Error listing tasks for robot {robot_id}: {e}")
            return []
