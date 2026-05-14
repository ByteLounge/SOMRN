# visualization/modes.py

MODES = {
    'beginner': {
        'label': '🟢 Beginner',
        'description': 'Plain English narration, no numbers',
        'show_metrics_panel': False,
        'show_qtable': False,
        'show_control_overhead': False,
        'show_narration_feed': True,
        'show_metrics_translation': True,
        'topology_label_style': 'emoji',
        'metrics_style': 'plain_english',
    },
    'intermediate': {
        'label': '🟡 Intermediate',
        'description': 'Simple gauges with plain English labels',
        'show_metrics_panel': True,
        'show_qtable': False,
        'show_control_overhead': False,
        'show_narration_feed': True,
        'show_metrics_translation': True,
        'topology_label_style': 'id',
        'metrics_style': 'gauges',
    },
    'expert': {
        'label': '🔴 Expert',
        'description': 'Full technical metrics and Q-table',
        'show_metrics_panel': True,
        'show_qtable': True,
        'show_control_overhead': True,
        'show_narration_feed': False,
        'show_metrics_translation': False,
        'topology_label_style': 'id',
        'metrics_style': 'technical',
    },
}

METRICS_TRANSLATIONS = {
    'pdr': {
        'label': 'Messages delivered',
        'format': lambda v: f"{v*100:.0f} out of every 100 messages arrive successfully",
        'good_threshold': 0.8,
        'unit': '%',
    },
    'avg_delay': {
        'label': 'Message travel time',
        'format': lambda v: f"Each message takes {v:.2f} seconds to cross the network",
        'good_threshold': 0.5,
        'unit': 's',
    },
    'route_breaks': {
        'label': 'Path disruptions',
        'format': lambda v: f"The path was disrupted {int(v)} times during this window",
        'good_threshold': 5,
        'unit': '',
    },
    'control_overhead': {
        'label': 'Protocol self-talk',
        'format': lambda v: f"{v*100:.0f}% of traffic is the protocol talking to itself",
        'good_threshold': 0.2,
        'unit': '%',
    },
    'throughput_bps': {
        'label': 'Data delivery speed',
        'format': lambda v: f"{v/1000:.1f} kilobits per second successfully delivered",
        'good_threshold': 5000,
        'unit': 'bps',
    },
}
