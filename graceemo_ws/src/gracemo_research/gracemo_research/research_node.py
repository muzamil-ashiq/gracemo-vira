#!/usr/bin/env python3
"""
GraceEMO — Research Experiment Framework
Define, run, and collect results from research experiments
on the LPU Digital Twin simulation platform.
"""

import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Experiment:
    """Represents a research experiment configuration and results."""

    def __init__(self, experiment_id: str, name: str, description: str):
        self.id = experiment_id
        self.name = name
        self.description = description
        self.state = 'created'  # created, running, completed, failed
        self.variables = {}
        self.baseline = {}
        self.test_conditions = []
        self.current_condition_idx = 0
        self.num_trials = 1
        self.current_trial = 0
        self.metrics_to_collect = []
        self.results = []
        self.started_at = None
        self.completed_at = None

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'state': self.state,
            'variables': self.variables,
            'baseline': self.baseline,
            'test_conditions': self.test_conditions,
            'current_condition_idx': self.current_condition_idx,
            'num_trials': self.num_trials,
            'current_trial': self.current_trial,
            'metrics_to_collect': self.metrics_to_collect,
            'results_count': len(self.results),
            'started_at': self.started_at,
            'completed_at': self.completed_at
        }


# Pre-built experiment templates
EXPERIMENT_TEMPLATES = {
    'cloud_vs_edge': {
        'name': 'Cloud vs Edge AI Performance',
        'description': 'How does network latency affect robot autonomous navigation?',
        'variables': {'network_latency_ms': [0, 50, 100, 250, 500]},
        'metrics': ['navigation_success_rate', 'mission_time', 'collision_count', 'server_dependency'],
        'num_trials': 3
    },
    'sensor_failure': {
        'name': 'Sensor Failure Resilience',
        'description': 'Can the robot maintain navigation when LiDAR/camera fails?',
        'variables': {'fault_type': ['lidar_failure', 'camera_failure', 'depth_sensor_failure', 'imu_failure']},
        'metrics': ['navigation_success_rate', 'collision_count', 'recovery_time', 'near_miss_count'],
        'num_trials': 5
    },
    'crowd_density': {
        'name': 'Crowded Campus Navigation',
        'description': 'How does pedestrian density affect navigation efficiency?',
        'variables': {'crowd_density': ['low', 'medium', 'high']},
        'metrics': ['navigation_time', 'distance_traveled', 'collision_count', 'near_miss_count', 'average_speed'],
        'num_trials': 3
    },
    'ai_offloading': {
        'name': 'AI Offloading Strategy',
        'description': 'When should the robot process locally vs use the central server?',
        'variables': {'server_mode': ['ONLINE', 'PARTIAL', 'OFFLINE']},
        'metrics': ['inference_latency', 'decision_quality', 'energy_consumption', 'mission_success_rate'],
        'num_trials': 3
    },
    'weather_impact': {
        'name': 'Weather Impact on Navigation',
        'description': 'How do different weather conditions affect sensor performance and navigation?',
        'variables': {'weather': ['clear_day', 'rain', 'fog', 'night']},
        'metrics': ['sensor_noise', 'navigation_success_rate', 'collision_count', 'average_speed'],
        'num_trials': 3
    }
}


class ResearchNode(Node):
    """
    Research experiment framework for the LPU Digital Twin.
    Supports creating, running, and collecting results from experiments.
    """

    def __init__(self):
        super().__init__('research_node')
        self.get_logger().info('🔬 Initializing Research Framework...')

        self.experiments: dict[str, Experiment] = {}
        self.active_experiment: Experiment | None = None
        self.experiment_counter = 0

        # Publishers
        self.research_state_pub = self.create_publisher(String, '/gracemo/research_state', 10)
        self.experiment_command_pub = self.create_publisher(String, '/gracemo/experiment_command', 10)

        # Subscribers
        self.create_subscription(String, '/gracemo/create_experiment', self.on_create_experiment, 10)
        self.create_subscription(String, '/gracemo/run_experiment', self.on_run_experiment, 10)
        self.create_subscription(String, '/gracemo/experiment_control', self.on_control, 10)
        self.create_subscription(String, '/gracemo/analytics', self.on_analytics, 10)

        # Timer
        self.create_timer(2.0, self.publish_state)
        self.create_timer(5.0, self.update_experiment)

        # Current analytics snapshot
        self.current_analytics = {}

        self.get_logger().info(f'✅ Research Framework ready — {len(EXPERIMENT_TEMPLATES)} pre-built templates')

    def on_create_experiment(self, msg: String):
        """Create an experiment from template or custom definition."""
        try:
            data = json.loads(msg.data)

            # Check if using a template
            template_name = data.get('template', '')
            if template_name in EXPERIMENT_TEMPLATES:
                tmpl = EXPERIMENT_TEMPLATES[template_name]
                data['name'] = data.get('name', tmpl['name'])
                data['description'] = data.get('description', tmpl['description'])
                data['variables'] = data.get('variables', tmpl['variables'])
                data['metrics'] = data.get('metrics', tmpl['metrics'])
                data['num_trials'] = data.get('num_trials', tmpl['num_trials'])

            self.experiment_counter += 1
            exp_id = f'exp_{self.experiment_counter:04d}'

            exp = Experiment(exp_id, data.get('name', 'Unnamed'), data.get('description', ''))
            exp.variables = data.get('variables', {})
            exp.metrics_to_collect = data.get('metrics', [])
            exp.num_trials = data.get('num_trials', 1)

            # Generate test conditions from variables
            for var_name, values in exp.variables.items():
                for val in values:
                    exp.test_conditions.append({var_name: val})

            self.experiments[exp_id] = exp
            self.get_logger().info(f'🔬 Experiment created: {exp_id} — {exp.name} ({len(exp.test_conditions)} conditions × {exp.num_trials} trials)')

        except Exception as e:
            self.get_logger().error(f'Failed to create experiment: {e}')

    def on_run_experiment(self, msg: String):
        """Start running an experiment."""
        exp_id = msg.data.strip()
        if exp_id not in self.experiments:
            self.get_logger().warn(f'Unknown experiment: {exp_id}')
            return

        exp = self.experiments[exp_id]
        exp.state = 'running'
        exp.started_at = time.time()
        exp.current_condition_idx = 0
        exp.current_trial = 0
        self.active_experiment = exp

        self.get_logger().info(f'🚀 Experiment started: {exp.name}')
        self._apply_condition(exp)

    def _apply_condition(self, exp: Experiment):
        """Apply the current test condition to the simulation."""
        if exp.current_condition_idx >= len(exp.test_conditions):
            exp.state = 'completed'
            exp.completed_at = time.time()
            self.active_experiment = None
            self.get_logger().info(f'✅ Experiment completed: {exp.name} — {len(exp.results)} results collected')
            return

        condition = exp.test_conditions[exp.current_condition_idx]
        self.get_logger().info(f'📝 Condition {exp.current_condition_idx + 1}/{len(exp.test_conditions)}, '
                              f'Trial {exp.current_trial + 1}/{exp.num_trials}: {condition}')

        # Publish commands to configure the simulation
        for var_name, value in condition.items():
            cmd = String()
            cmd.data = json.dumps({
                'experiment_id': exp.id,
                'variable': var_name,
                'value': value,
                'condition_idx': exp.current_condition_idx,
                'trial': exp.current_trial
            })
            self.experiment_command_pub.publish(cmd)

    def update_experiment(self):
        """Update running experiment — collect metrics and advance conditions."""
        if self.active_experiment is None or self.active_experiment.state != 'running':
            return

        exp = self.active_experiment

        # Collect metrics snapshot
        result = {
            'condition_idx': exp.current_condition_idx,
            'condition': exp.test_conditions[exp.current_condition_idx] if exp.current_condition_idx < len(exp.test_conditions) else {},
            'trial': exp.current_trial,
            'timestamp': time.time(),
            'metrics': dict(self.current_analytics)
        }
        exp.results.append(result)

        # Advance trial
        exp.current_trial += 1
        if exp.current_trial >= exp.num_trials:
            exp.current_trial = 0
            exp.current_condition_idx += 1
            self._apply_condition(exp)

    def on_control(self, msg: String):
        """Handle experiment control commands: stop, pause."""
        cmd = msg.data.strip().lower()
        if cmd == 'stop' and self.active_experiment:
            self.active_experiment.state = 'completed'
            self.active_experiment.completed_at = time.time()
            self.get_logger().info(f'🛑 Experiment stopped: {self.active_experiment.name}')
            self.active_experiment = None

    def on_analytics(self, msg: String):
        """Receive analytics data for experiment metric collection."""
        try:
            self.current_analytics = json.loads(msg.data)
        except Exception:
            pass

    def publish_state(self):
        """Publish research framework state."""
        state = {
            'active_experiment': self.active_experiment.to_dict() if self.active_experiment else None,
            'experiments': {eid: e.to_dict() for eid, e in self.experiments.items()},
            'templates_available': list(EXPERIMENT_TEMPLATES.keys()),
            'total_experiments': len(self.experiments)
        }
        msg = String()
        msg.data = json.dumps(state)
        self.research_state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ResearchNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
