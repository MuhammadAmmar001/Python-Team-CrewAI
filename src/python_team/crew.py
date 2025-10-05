from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

@CrewBase
class PythonTeam():
    """PythonTeam crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def engineering_lead(self) -> Agent:
        return Agent(
            config = self.agents_config['engineering_lead'],
            verbose = True
        )
    
    @agent
    def backend_python_developer(self) -> Agent:
        return Agent(
            config = self.agents_config['backend_python_developer'],
            verbose=True,
            allow_code_execution=True,
            code_execution_mode="safe",
            max_execution_time=1000,
            max_retry_limit=2
        )
    @agent
    def frontend_python_developer(self) -> Agent:
        return Agent(
            config = self.agents_config['frontend_python_developer'],
            verbose=True
        )
    @agent
    def QA_engineer(self) -> Agent:
        return Agent(
            config = self.agents_config['QA_engineer'],
            verbose=True,
            allow_code_execution=True,
            code_execution_mode="safe",
            max_execution_time=1000,
            max_retry_limit=2
        )
    @task
    def plan_design(self) -> Task:
        return Task(
            config=self.tasks_config['plan_design']
        )
    @task
    def code_backend(self) -> Task:
        return Task(
            config=self.tasks_config['code_backend']
        )
    @task
    def code_frontend(self) -> Task:
        return Task(
            config=self.tasks_config['code_frontend']
        )
    @task
    def test_backend(self) -> Task:
        return Task(
            config=self.tasks_config['test_backend']
        )

    @crew
    def crew(self) -> Crew:
        """Creates the PythonTeam crew"""
        
        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
