import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--test')
parser.add_argument('--other')
args = parser.parse_args()

print('Running')
print(args.other)
