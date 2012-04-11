#@PydevCodeAnalysisIgnore
Feature: Test RGlob
	Provide confidence that rglob works
	Scenario: Create 2 Temp Directories
		Given I create a root directory
		Then I find 0 total directories
		
	Scenario: Create 10 Temp Directories
		Given I create a root directory
		Given I create 10 subdirectories in each directory
		Then I find 10 total directories
		Then I delete all
		Then I find 0 total directories
		
	Scenario: Create 110 Temp Directories
		Given I create a root directory
		Given I create 10 subdirectories in each directory
		Given I create 10 subdirectories in each directory
		Then I find 110 total directories
		Then I delete all
		
	Scenario: Create 1100 Temp Directories
		Given I create a root directory
		Given I create 100 subdirectories in each directory
		Given I create 10 subdirectories in each directory
		Then I find 1100 total directories
		Then I delete all
		Then I find 0 total directories
		
	Scenario: Create 1100 Temp Text Files
		Given I create a root directory
		Given I create 100 subdirectories in each directory
		Given I create 10 subdirectories in each directory
		Given I create 1 .txt files in each directory
		Then I find 1100 total directories
		Then I find 1100 total .txt files
		Given I sum .txt files known sizes
		Then I can find the same size for .txt
		Then I delete all
		Then I find 0 total directories