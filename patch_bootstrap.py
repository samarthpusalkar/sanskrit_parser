import re

with open("data/rule_config_bootstrap.py", "r") as f:
    content = f.read()

content = "import sys, os\nsys.path.insert(0, os.path.abspath('.'))\n" + content

with open("data/rule_config_bootstrap.py", "w") as f:
    f.write(content)
