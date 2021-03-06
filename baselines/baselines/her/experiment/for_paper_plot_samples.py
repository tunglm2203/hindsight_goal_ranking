# DEPRECATED, use baselines.common.plot_util instead

import os
import matplotlib.pyplot as plt
import numpy as np
import json
import seaborn as sns; sns.set()
import glob2
import argparse
import matplotlib.ticker as mtick


def smooth_reward_curve(x, y):
    halfwidth = int(np.ceil(len(x) / 60))  # Halfwidth of our smoothing convolution
    k = halfwidth
    xsmoo = x
    ysmoo = np.convolve(y, np.ones(2 * k + 1), mode='same') / np.convolve(np.ones_like(y), np.ones(2 * k + 1),
                                                                          mode='same')
    return xsmoo, ysmoo


def load_results(file):
    if not os.path.exists(file):
        return None
    with open(file, 'r') as f:
        lines = [line for line in f]
    if len(lines) < 2:
        return None
    keys = [name.strip() for name in lines[0].split(',')]
    data = np.genfromtxt(file, delimiter=',', skip_header=1, filling_values=0.)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    assert data.ndim == 2
    assert data.shape[-1] == len(keys)
    result = {}
    for idx, key in enumerate(keys):
        result[key] = data[:, idx]
    return result


def pad(xs, value=np.nan):
    maxlen = np.max([len(x) for x in xs])

    padded_xs = []
    for x in xs:
        if x.shape[0] >= maxlen:
            padded_xs.append(x)

        padding = np.ones((maxlen - x.shape[0],) + x.shape[1:]) * value
        x_padded = np.concatenate([x, padding], axis=0)
        assert x_padded.shape[1:] == x.shape[1:]
        assert x_padded.shape[0] == maxlen
        padded_xs.append(x_padded)
    return np.array(padded_xs)


parser = argparse.ArgumentParser()
parser.add_argument('--dir', type=str, nargs='+')
parser.add_argument('--smooth', type=int, default=1)
parser.add_argument('--range', type=int, default=-1, help='Number of transitions want to plot')
parser.add_argument('--legend', type=str, default='', nargs='+')
parser.add_argument('--thresh', type=float, default=0.9)
args = parser.parse_args()


directory = []
for i in range(len(args.dir)):
    if args.dir[i][-1] == '/':
        directory.append(args.dir[i][:-1])
    else:
        directory.append(args.dir[i])
collect_data = []


for dir in directory:
    args.dir = dir
    data = {}
    paths = [os.path.abspath(os.path.join(path, '..')) for path in glob2.glob(os.path.join(args.dir, '**',
                                                                                           'progress.csv'))]
    for curr_path in paths:
        if not os.path.isdir(curr_path):
            continue
        results = load_results(os.path.join(curr_path, 'progress.csv'))
        if not results:
            print('skipping {}'.format(curr_path))
            continue
        print('loading {} ({})'.format(curr_path, len(results['time_step'])))
        with open(os.path.join(curr_path, 'params.json'), 'r') as f:
            params = json.load(f)

        success_rate = np.array(results['test/success_rate'])
        epoch = np.array(results['time_step']) + 1
        env_id = params['env_name']
        replay_strategy = params['replay_strategy']

        if replay_strategy == 'future':
            config = 'her'
        else:
            config = 'ddpg'
        if 'Dense' in env_id:
            config += '-dense'
        else:
            config += '-sparse'
        env_id = env_id.replace('Dense', '')

        # Process and smooth data.
        assert success_rate.shape == epoch.shape
        x = epoch
        y = success_rate
        if args.smooth:
            x, y = smooth_reward_curve(epoch, success_rate)
        assert x.shape == y.shape

        if env_id not in data:
            data[env_id] = {}
        if config not in data[env_id]:
            data[env_id][config] = []
        data[env_id][config].append((x, y))
    collect_data.append(data)

# Plot data.
plt.figure()
ax = plt.subplot()
for i in range(len(collect_data)):
    data = collect_data[i]
    for env_id in sorted(data.keys()):
        print('exporting {}'.format(env_id))
        # plt.clf()

        for config in sorted(data[env_id].keys()):
            xs, ys = zip(*data[env_id][config])
            n_experiments = len(xs)
            if args.range != -1:
                _xs = []
                _ys = []
                for k in range(n_experiments):
                    _xs.append(xs[k][:args.range])
                    _ys.append(ys[k][:args.range])
                xs = _xs
                ys = _ys
            xs, ys = pad(xs), pad(ys)
            ys = np.mean(ys, axis=0)
            assert xs[0].shape == ys.shape
            _ys = np.zeros_like(ys)
            cur_success_rate = 0.0
            for k in range(ys.shape[0]):
                if ys[k] > cur_success_rate:
                    _ys[k] = ys[k]
                    cur_success_rate = ys[k]
                else:
                    _ys[k] = cur_success_rate

            ys = _ys
            idx = np.where(ys > args.thresh)[0][0]
            plt.plot(ys[:idx], xs[0][:idx], label=config)
            # plt.fill_between(xs[0], np.nanpercentile(ys, 25, axis=0), np.nanpercentile(ys, 75, axis=0), alpha=0.25)
            plt.xlabel('Median Success Rate', fontsize=10)
        plt.title(env_id, fontsize=10)
        plt.ylabel('#Environment interactions', fontsize=10)
        # ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.e'))
        plt.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
        # plt.ylim([0, 1.05])
        plt.xlim([0, 0.9])

if args.legend != '':
    assert len(args.legend) == len(directory), "Provided legend is not match with number of directories"
    legend_name = args.legend
else:
    legend_name = [directory[i].split('/')[-1] for i in range(len(directory))]
plt.legend(legend_name)

plt.savefig(os.path.join('logs', 'fig_{}.pdf'.format(env_id)), quality=100)
plt.show()
