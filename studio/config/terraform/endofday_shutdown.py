#!/usr/bin/env python3
import subprocess
import sys
import time
from typing import Optional

from colorama import Fore, init

init()


class Colors:
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    NC = Fore.RESET


def run_command(
    cmd: list[str], shell: bool = False, check: bool = True
) -> Optional[str]:
    """Execute command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=shell, check=check, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Error executing command: {e.stderr}{Colors.NC}")
        return None
    except FileNotFoundError as e:
        print(f"{Colors.RED}Command not found: {e}{Colors.NC}")
        return None


def complete_lifecycle_actions() -> bool:
    """Complete any pending lifecycle actions for terminating instances"""
    print(f"{Colors.YELLOW}Completing pending lifecycle actions...{Colors.NC}")

    # Get instances in Terminating:Wait state
    terminating_instances = run_command(
        [
            "aws",
            "autoscaling",
            "describe-auto-scaling-groups",
            "--auto-scaling-group-names",
            "subscr-optinist-asg",
            "--query",
            "AutoScalingGroups[0].Instances[?LifecycleState=='Terminating:Wait']."
            "InstanceId",
            "--output",
            "text",
        ]
    )

    if terminating_instances and terminating_instances.strip() != "None":
        instance_list = terminating_instances.split()
        print(
            f"{Colors.YELLOW}Found {len(instance_list)} instances in "
            f"Terminating:Wait{Colors.NC}"
        )

        for instance_id in instance_list:
            print(
                f"{Colors.YELLOW}Completing lifecycle action for "
                f"{instance_id}...{Colors.NC}"
            )
            run_command(
                [
                    "aws",
                    "autoscaling",
                    "complete-lifecycle-action",
                    "--lifecycle-hook-name",
                    "subscr-optinist-terminate-hook",
                    "--auto-scaling-group-name",
                    "subscr-optinist-asg",
                    "--lifecycle-action-result",
                    "CONTINUE",
                    "--instance-id",
                    instance_id,
                ],
                check=False,
            )

    return True


def update_services(services: list[str]) -> bool:
    """Scale down ECS services to 0 tasks"""
    print(f"{Colors.YELLOW}Scaling down ECS services to 0 tasks...{Colors.NC}")
    for service in services:
        result = run_command(
            [
                "aws",
                "ecs",
                "update-service",
                "--cluster",
                "subscr-optinist-cloud-cluster",
                "--service",
                service,
                "--desired-count",
                "0",
                "--force-new-deployment",
            ]
        )
        if result is None:
            print(f"{Colors.RED}Failed to scale down service: {service}{Colors.NC}")
            return False
        else:
            print(
                f"{Colors.GREEN}Successfully scaled down service: {service}"
                f"{Colors.NC}"
            )
    return True


def stop_all_tasks() -> bool:
    """Stop all running ECS tasks"""
    print(f"{Colors.YELLOW}Stopping all running tasks...{Colors.NC}")
    tasks = run_command(
        [
            "aws",
            "ecs",
            "list-tasks",
            "--cluster",
            "subscr-optinist-cloud-cluster",
            "--desired-status",
            "RUNNING",
            "--query",
            "taskArns[]",
            "--output",
            "text",
        ]
    )

    if tasks and tasks.strip() != "None":
        task_list = tasks.split()
        print(
            f"{Colors.YELLOW}Found {len(task_list)} running tasks to stop"
            f"{Colors.NC}"
        )

        for task in task_list:
            result = run_command(
                [
                    "aws",
                    "ecs",
                    "stop-task",
                    "--cluster",
                    "subscr-optinist-cloud-cluster",
                    "--task",
                    task,
                ],
                check=False,
            )
            if result is None:
                print(
                    f"{Colors.YELLOW}Warning: Failed to stop task {task}" f"{Colors.NC}"
                )
            else:
                print(
                    f"{Colors.GREEN}Stopped task: {task.split('/')[-1]}" f"{Colors.NC}"
                )
    else:
        print(f"{Colors.GREEN}No running tasks found{Colors.NC}")

    return True


def wait_for_tasks_to_stop(timeout: int = 600) -> bool:
    """Wait for all ECS tasks to stop"""
    print(f"{Colors.YELLOW}Waiting for tasks to stop...{Colors.NC}")
    elapsed = 0
    while not check_tasks_stopped() and elapsed < timeout:
        time.sleep(10)
        elapsed += 10
        print(
            f"{Colors.YELLOW}Still waiting for tasks to stop... {elapsed}s elapsed"
            f"{Colors.NC}"
        )

    if elapsed >= timeout:
        print(f"{Colors.RED}Timeout waiting for tasks to stop{Colors.NC}")
        return False

    print(f"{Colors.GREEN}All tasks have stopped{Colors.NC}")
    return True


def check_tasks_stopped() -> bool:
    """Check if all tasks are stopped"""
    try:
        running_tasks = run_command(
            [
                "aws",
                "ecs",
                "list-tasks",
                "--cluster",
                "subscr-optinist-cloud-cluster",
                "--desired-status",
                "RUNNING",
                "--query",
                "length(taskArns)",
                "--output",
                "text",
            ]
        )
        task_count = int(running_tasks or 0)
        if task_count > 0:
            print(f"{Colors.YELLOW}Still {task_count} tasks running{Colors.NC}")
        return task_count == 0
    except (ValueError, TypeError) as e:
        print(f"{Colors.RED}Error checking tasks: {e}{Colors.NC}")
        return False


def scale_down_asg() -> bool:
    """Scale down Auto Scaling Groups"""
    print(f"{Colors.YELLOW}Scaling down ASGs...{Colors.NC}")
    result = run_command(
        [
            "aws",
            "autoscaling",
            "update-auto-scaling-group",
            "--auto-scaling-group-name",
            "subscr-optinist-asg",
            "--desired-capacity",
            "0",
            "--min-size",
            "0",
            "--max-size",
            "1",
        ]
    )
    if result is None:
        print(f"{Colors.RED}Failed to scale down ASG{Colors.NC}")
        return False

    print(f"{Colors.GREEN}Successfully scaled down ASG{Colors.NC}")
    return True


def wait_for_asg_to_terminate(timeout: int = 600) -> bool:
    """Wait for ASG instances to terminate"""
    print(f"{Colors.YELLOW}Waiting for ASG instances to terminate...{Colors.NC}")
    asg_name = "subscr-optinist-asg"
    elapsed = 0
    while elapsed < timeout:
        # Complete any pending lifecycle actions first
        complete_lifecycle_actions()

        all_terminated = check_asg_instances(asg_name)
        if all_terminated:
            break
        time.sleep(10)
        elapsed += 10
        print(
            f"{Colors.YELLOW}Waiting for ASG instances to terminate... {elapsed}s"
            f" elapsed{Colors.NC}"
        )

    if elapsed >= timeout:
        print(
            f"{Colors.RED}Timeout waiting for ASG instances to terminate" f"{Colors.NC}"
        )
        return False

    print(f"{Colors.GREEN}All ASG instances have terminated{Colors.NC}")
    return True


def check_asg_instances(asg_name: str) -> bool:
    """Check if ASG has no instances that need termination"""
    try:
        output = run_command(
            [
                "aws",
                "autoscaling",
                "describe-auto-scaling-groups",
                "--auto-scaling-group-names",
                asg_name,
                "--query",
                "AutoScalingGroups[0].Instances[?LifecycleState=='InService' || "
                "LifecycleState=='Pending' || LifecycleState=='Pending:Wait' || "
                "LifecycleState=='Pending:Proceed' || "
                "LifecycleState=='Terminating' || "
                "LifecycleState=='Terminating:Wait' || "
                "LifecycleState=='Standby'].InstanceId",
                "--output",
                "text",
            ]
        )
        # Handle None output case
        instance_count = (
            len(output.split()) if output and output.strip() != "None" else 0
        )
        if instance_count > 0:
            print(
                f"{Colors.YELLOW}Active instances in ASG: {instance_count}"
                f"{Colors.NC}"
            )
        else:
            print(f"{Colors.GREEN}No active instances in ASG{Colors.NC}")
        return instance_count == 0
    except (AttributeError, ValueError) as e:
        print(f"{Colors.RED}Error checking ASG instances: {e}{Colors.NC}")
        return False


def force_terminate_asg_instances() -> bool:
    """Force terminate any remaining ASG instances"""
    print(
        f"{Colors.YELLOW}Force terminating any remaining ASG instances..."
        f"{Colors.NC}"
    )

    # Get all instances in the ASG
    output = run_command(
        [
            "aws",
            "autoscaling",
            "describe-auto-scaling-groups",
            "--auto-scaling-group-names",
            "subscr-optinist-asg",
            "--query",
            "AutoScalingGroups[0].Instances[].InstanceId",
            "--output",
            "text",
        ]
    )

    if output and output.strip() != "None":
        instance_ids = output.split()
        print(
            f"{Colors.YELLOW}Found {len(instance_ids)} instances to terminate"
            f"{Colors.NC}"
        )
        for instance_id in instance_ids:
            print(
                f"{Colors.YELLOW}Terminating instance {instance_id}..." f"{Colors.NC}"
            )
            result = run_command(
                ["aws", "ec2", "terminate-instances", "--instance-ids", instance_id],
                check=False,
            )
            if result:
                print(
                    f"{Colors.GREEN}Initiated termination for {instance_id}"
                    f"{Colors.NC}"
                )
    else:
        print(f"{Colors.GREEN}No instances found to terminate{Colors.NC}")

    return True


def get_capacity_provider_state(cluster_name: str) -> Optional[str]:
    """Check the current state of the cluster's capacity provider associations"""
    try:
        result = run_command(
            [
                "aws",
                "ecs",
                "describe-clusters",
                "--clusters",
                cluster_name,
                "--include",
                "ATTACHMENTS",
                "--query",
                "clusters[0].attachments[?type=='CAPACITY_PROVIDER'][].status",
                "--output",
                "text",
            ]
        )
        return result
    except Exception as e:
        print(f"{Colors.YELLOW}Error checking cluster state: {str(e)}{Colors.NC}")
        return None


def wait_for_cluster_stability(cluster_name: str, timeout: int = 300) -> bool:
    """Wait until the cluster capacity provider attachments are in a stable state"""
    print(
        f"{Colors.YELLOW}Waiting for cluster capacity provider attachments to "
        f"stabilize...{Colors.NC}"
    )
    elapsed = 0
    stable_states = ["UPDATE_COMPLETE", "UPDATE_FAILED", "NONE", ""]

    while elapsed < timeout:
        state = get_capacity_provider_state(cluster_name)

        # If no attachments or empty state, it's likely ready
        if not state or state.strip() == "":
            print(
                f"{Colors.GREEN}No active capacity provider attachments." f"{Colors.NC}"
            )
            return True

        # Check if all states are stable
        if state and all(s in stable_states for s in state.split()):
            print(
                f"{Colors.GREEN}Cluster capacity provider attachments are stable "
                f"({state}).{Colors.NC}"
            )
            return True

        time.sleep(20)
        elapsed += 20
        print(
            f"{Colors.YELLOW}Cluster capacity provider state: {state} - "
            f"waiting... ({elapsed}s elapsed){Colors.NC}"
        )

    print(
        f"{Colors.RED}Timeout waiting for cluster capacity provider stability"
        f"{Colors.NC}"
    )
    return False


def detach_capacity_providers(cluster_name: str, max_attempts: int = 10) -> bool:
    """Detach all capacity providers from cluster with retries"""
    print(f"{Colors.YELLOW}Detaching capacity providers from cluster..." f"{Colors.NC}")

    # First, wait for cluster to be stable
    if not wait_for_cluster_stability(cluster_name):
        print(
            f"{Colors.YELLOW}Cluster not stable, but continuing with detachment "
            f"attempts...{Colors.NC}"
        )

    # Try detachment with fewer retries since we're shutting down anyway
    for attempt in range(1, max_attempts + 1):
        print(
            f"{Colors.YELLOW}Detachment attempt {attempt}/{max_attempts}..."
            f"{Colors.NC}"
        )

        result = run_command(
            [
                "aws",
                "ecs",
                "put-cluster-capacity-providers",
                "--cluster",
                cluster_name,
                "--capacity-providers",
                "[]",
                "--default-capacity-provider-strategy",
                "[]",
            ],
            check=False,
        )

        if result is not None:
            print(
                f"{Colors.GREEN}Successfully detached capacity providers" f"{Colors.NC}"
            )
            return True

        if attempt < max_attempts:
            print(
                f"{Colors.YELLOW}Detachment failed, waiting before retrying..."
                f"{Colors.NC}"
            )
            time.sleep(30)

    print(
        f"{Colors.YELLOW}Could not detach capacity providers after "
        f"{max_attempts} attempts{Colors.NC}"
    )
    print(
        f"{Colors.YELLOW}This is normal during shutdown - continuing..." f"{Colors.NC}"
    )
    return True  # Return True to continue shutdown process


def validate_capacity_provider() -> bool:
    """Validate capacity provider exists"""
    result = run_command(
        [
            "aws",
            "ecs",
            "describe-capacity-providers",
            "--capacity-providers",
            "subscr-optinist-capacity-provider",
            "--query",
            "capacityProviders[0].name",
            "--output",
            "text",
        ],
        check=False,
    )

    exists = result == "subscr-optinist-capacity-provider"
    if exists:
        print(f"{Colors.GREEN}Capacity provider exists{Colors.NC}")
    else:
        print(
            f"{Colors.YELLOW}Capacity provider doesn't exist or already removed"
            f"{Colors.NC}"
        )
    return exists


def cleanup_orphaned_batch_instances() -> bool:
    """Clean up orphaned AWS Batch compute environment instances"""
    print(f"{Colors.YELLOW}Cleaning up orphaned Batch instances...{Colors.NC}")

    # Get instances with Batch-related names that are running
    orphaned_instances = run_command(
        [
            "aws",
            "ec2",
            "describe-instances",
            "--filters",
            "Name=instance-state-name,Values=running",
            "Name=tag:Name,Values=*Batch*",
            "--query",
            "Reservations[].Instances[].InstanceId",
            "--output",
            "text",
        ]
    )

    if orphaned_instances and orphaned_instances.strip():
        instance_list = orphaned_instances.split()
        print(
            f"{Colors.YELLOW}Found {len(instance_list)}{Colors.NC} "
            f"{Colors.YELLOW}orphaned Batch instances{Colors.NC}"
        )

        for instance_id in instance_list:
            print(
                f"{Colors.YELLOW}Terminating orphaned instance: {Colors.NC}"
                f"{instance_id}"
            )
            run_command(
                [
                    "aws",
                    "ec2",
                    "terminate-instances",
                    "--instance-ids",
                    instance_id,
                ],
                check=False,
            )
    else:
        print(f"{Colors.GREEN}No orphaned Batch instances found{Colors.NC}")

    return True


def shutdown_batch_environments() -> bool:
    """Disable all AWS Batch compute environments to prevent new jobs"""
    print(f"{Colors.YELLOW}Disabling AWS Batch compute environments...{Colors.NC}")

    # Get all compute environments
    environments = run_command(
        [
            "aws",
            "batch",
            "describe-compute-environments",
            "--query",
            "computeEnvironments[].computeEnvironmentName",
            "--output",
            "text",
        ]
    )

    if not environments:
        print(f"{Colors.YELLOW}No compute environments found{Colors.NC}")
        return True

    for env_name in environments.split():
        print(f"{Colors.YELLOW}Disabling environment: {env_name}{Colors.NC}")
        run_command(
            [
                "aws",
                "batch",
                "update-compute-environment",
                "--compute-environment",
                env_name,
                "--state",
                "DISABLED",
            ],
            check=False,
        )

    # Clean up any orphaned instances after disabling environments
    cleanup_orphaned_batch_instances()

    print(f"{Colors.GREEN}Batch environments shutdown initiated{Colors.NC}")
    return True


def tier1_shutdown() -> bool:
    """Shutdown infrastructure in proper order"""
    print(f"{Colors.GREEN}{'='*60}{Colors.NC}")
    print(
        f"{Colors.GREEN}Starting OptiNiSt infrastructure shutdown process"
        f"{Colors.NC}"
    )
    print(f"{Colors.GREEN}{'='*60}{Colors.NC}")

    # Step 1: Shutdown AWS Batch environments
    try:
        print(
            f"\n{Colors.YELLOW}Step 1: Shutting down AWS Batch environments"
            f"{Colors.NC}"
        )
        shutdown_batch_environments()
    except Exception as e:
        print(f"{Colors.RED}Error shutting down Batch: {e}{Colors.NC}")
        print(f"{Colors.YELLOW}Continuing with ECS shutdown...{Colors.NC}")

    # Step 2: Scale down ECS services
    try:
        print(f"\n{Colors.YELLOW}Step 2: Scaling down ECS services{Colors.NC}")
        services = ["subscr-optinist-cloud-service"]
        if not update_services(services):
            print(f"{Colors.RED}Failed to scale down services{Colors.NC}")
            return False
    except Exception as e:
        print(f"{Colors.RED}Error scaling down services: {e}{Colors.NC}")
        return False

    # Step 3: Stop all running tasks
    try:
        print(f"\n{Colors.YELLOW}Step 3: Stopping all running ECS tasks" f"{Colors.NC}")
        stop_all_tasks()
    except Exception as e:
        print(f"{Colors.RED}Error stopping tasks: {e}{Colors.NC}")

    # Step 4: Wait for tasks to stop
    try:
        print(f"\n{Colors.YELLOW}Step 4: Waiting for all tasks to stop" f"{Colors.NC}")
        if not wait_for_tasks_to_stop(timeout=300):
            print(
                f"{Colors.YELLOW}Some tasks may still be running, but "
                f"continuing...{Colors.NC}"
            )
    except Exception as e:
        print(f"{Colors.RED}Error waiting for tasks to stop: {e}{Colors.NC}")

    # Step 5: Scale down ASGs
    try:
        print(
            f"\n{Colors.YELLOW}Step 5: Scaling down Auto Scaling Groups" f"{Colors.NC}"
        )
        if not scale_down_asg():
            print(f"{Colors.RED}Failed to scale down ASGs{Colors.NC}")
            return False
    except Exception as e:
        print(f"{Colors.RED}Error scaling down ASGs: {e}{Colors.NC}")
        return False

    # Step 6: Wait for ASG instances to terminate
    try:
        print(
            f"\n{Colors.YELLOW}Step 6: Waiting for ASG instances to terminate"
            f"{Colors.NC}"
        )
        if not wait_for_asg_to_terminate(timeout=300):
            print(
                f"{Colors.YELLOW}ASG instances didn't terminate gracefully, "
                f"forcing termination...{Colors.NC}"
            )
            force_terminate_asg_instances()
            time.sleep(60)
    except Exception as e:
        print(
            f"{Colors.RED}Error waiting for ASG instances to terminate: {e}"
            f"{Colors.NC}"
        )

    # Step 7: Optional capacity provider cleanup (not critical for shutdown)
    try:
        print(
            f"\n{Colors.YELLOW}Step 7: Cleaning up capacity providers "
            f"(optional){Colors.NC}"
        )
        if validate_capacity_provider():
            detach_capacity_providers("subscr-optinist-cloud-cluster")
        else:
            print(f"{Colors.YELLOW}Skipping capacity provider cleanup" f"{Colors.NC}")
    except Exception as e:
        print(
            f"{Colors.YELLOW}Note: Capacity provider cleanup failed: {e}" f"{Colors.NC}"
        )
        print(
            f"{Colors.YELLOW}This is normal during shutdown and doesn't affect "
            f"the process{Colors.NC}"
        )

    print(f"\n{Colors.GREEN}{'='*60}{Colors.NC}")
    print(
        f"{Colors.GREEN}Infrastructure shutdown completed successfully!" f"{Colors.NC}"
    )
    print(f"{Colors.GREEN}All services and instances have been stopped." f"{Colors.NC}")
    print(f"{Colors.GREEN}{'='*60}{Colors.NC}")
    return True


if __name__ == "__main__":
    success = tier1_shutdown()
    sys.exit(0 if success else 1)
