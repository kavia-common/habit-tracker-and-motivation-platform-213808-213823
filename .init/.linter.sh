#!/bin/bash
cd /home/kavia/workspace/code-generation/habit-tracker-and-motivation-platform-213808-213823/habithive_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

