from bulldog.bulldog import Model, Version
import pandas as pd
import time
import pickle


def on_checkpoint_save(data, key, history):
    file_name = 'data_{}.pkl'.format(key.step)
    pickle.dump(data, open('data_{}.pkl'.format(key.step), 'wb'))
    return file_name  # only the file name will be saved in memory


def on_checkpoint_restore(key, history):
    file_name = history[key]
    return pickle.load(open(file_name, 'rb'))  # store this in model.data


model = Model(
    data={
        'df': pd.DataFrame(pd.np.ones((100, 100))),
    },
    on_checkpoint_save=on_checkpoint_save,
    on_checkpoint_restore=on_checkpoint_restore
)


@model.data_modifier
def data_step(data, factor):
    df = data['df']
    df *= factor
    return data  # this will modify the data


@model.business_logic
@model.checkpoint
def action1(data, commit):
    data['df'] /= 8000  # this has no effect whatsoever, we are modifying a copy
    commit("data_step", 9)
    return data  # consequently this does nothing


@model.analysis
@model.parallelizable
def analysis(data, history):
    df = data['df']
    time.sleep(3)
    print('fast 1', list(history.keys())[-1].name, pd.np.mean(df.values))


@model.analysis
@model.parallelizable
def analysis2(data, history):
    df = data['df']
    time.sleep(3)
    print('fast 2', list(history.keys())[-1].name, pd.np.mean(df.values))


@model.analysis
def analysis3(data, history):
    df = data['df']
    time.sleep(3)
    print('slow', list(history.keys())[-1].name, pd.np.mean(df.values))


def main():
    model.dispatch('action1')
    model.commit('data_step', factor=9)
    print(model.history.keys())
    model.revert_version(Version(name='action1', step=1))
    # or equivalently `model.rollback(2)`
    print(model.history.keys())


if __name__ == '__main__':
    main()
