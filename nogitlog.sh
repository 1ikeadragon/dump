#!/bin/bash

read -p "Enter the branch name to purge: " branch_name

git checkout --orphan temp_branch

git add -A
git reset -- "$0"

git commit -m "Purged commits"

git branch -D "$branch_name"

git branch -m "$branch_name"

git push -f origin "$branch_name"
