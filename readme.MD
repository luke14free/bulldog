# Bulldog

The guardian dog that prevents you from writing poor code when doing data analysis in Python.

## Installation

Simply run:

`pip install bulldog`

## Philosophy

Bulldog is a library for writing better code in your analysis that largely borrows from the state management libraries for application development ([Redux](https://github.com/reduxjs/redux), [Flux](https://github.com/facebook/flux), [Vuex](https://github.com/vuejs/vuex), [Katana](https://github.com/BendingSpoons/katana-swift)..).

Bulldog models are composed of five main building blocks:
1) `data`, which is our model initial data
2) `data_modifiers`, which are special function whose main task is to modify the model's data
3) `business_logic`, which are function whose main task is to execute the business logic and invoke `data_modifiers`
4) `analyses`, which subscribe to change on the model's `data`
5) `history`, which is a backlog of all the operations that have occurred and the corresponding state of the model `data`

The philosophy behind bulldog is to **separate** data transformations, business logic and analyses, in order to make
clarity, testing and debugging easier to achieve.

## Working with bulldog

To create a bulldog model simply run:
```python
from bulldog.model import Model
import pandas as pd

model = Model(data={
    'df': pd.DataFrame(pd.np.ones((100, 100))),
    'other_data': [1, 2, 3]
})
```

All the data is stored in our `model.data` and it's not directly modifiable. In fact, whenever we access `model.data` we are actually accessing a copy of the original model data.

In order to alter/modify our data we need to create some special functions called `data_modifiers`.

```python
@model.data_modifier
def data_step(data, factor):
    df = data['df']
    df *= factor
    return data  # this will modify the data
```

As we can see data modifiers are just simple, pure functions that take our model data as input and perform some kind of alteration on it 
and return the altered data. The signature of a business model is `function(data, *args, **kwargs)` and it needs to be
decorated with the `@model.data_modifier` decorator (where `model` is your instance of Bulldog's `Model`).

If we want to execute a `data_modifier`, rather than calling it directly we need to ask the model to commit it:

```python
model.commit('data_step', factor=9)  # 'data_step' is the name of our `data_modifier`
```

Note that any other way of calling the function will result in an error. E.g.:

```python
data_step(data=model.data, factor=9)  # wrong; this will throw an error
```

Great! but what if we need to run some business logic to conditionally modify our dataset?
Maybe we need to download some data and based on that perform some actions that will eventually 
lead us to modify our data. In this case we should use a `business_logic` function.

```python
@model.business_logic
@model.checkpoint
def action1(data, commit):
    data['df'] /= 8000  # this has no effect whatsoever on our data, remember? We are modifying a copy
    if max(data['df']) < 0.38:
        commit("data_step", 9)  # but this will actually modify our data
```

As we can see `business_logic` are function with the signature `function(data, commit, *args, **kwargs)` which take as input the data
and have the possibility of committing `data_modifier` functions to our original model

You might have noted the additional `@model.checkpoint` decorator (which can also be applied to `data_modifiers`). It will basically tell our model to store the current state data after computing
this function (and store it in `model.history`), allowing us to restore it or inspect it at a later stage, which is very convenient for debugging.

Similarly to `data_modifiers`, also `business_logic` cannot be execute directly, and have to be dispatched through the model in this way:

```python
model.dispatch('action1')
```

Now, you might wonder how to run analyses on the model's data. That's fairly simple!

```python
@model.analysis
@model.parallelizable
def analysis(data, history):
    df = data['df']
    time.sleep(3)
    print('fast 1', list(history.keys())[-1].name, pd.np.mean(df.values))
```

Analyses are functions with signature `function(data, history)` that are run automatically every time a checkpoint step of our model is executed.
Optionally analyses can be run in parallel (if you use the `@model.parallelizable` decorator, as above). This is particularly convenient
in case we are computing a large number of metrics and want to leverage our CPU as much as possible.
Note that only analyses can be parallelized in Bulldog.

### Custom checkpoints management

Out of the box, Bulldog doesn't implement any custom diffing logic for the model `data` (since it's a generic dictionary which could contain anything),
but you can provide your own functions to checkpoint & restore your data. For example you might want to write/read:

1) from a database
2) from a pickled file on disk
3) from h5df
3) diffs from custom diffing tools (or generic ones like [csv-diff](https://github.com/aswinkarthik/csvdiff))

If you want to provide some custom save/load logic to handle checkpoint save & restore, pass these two functions to the Model initializer:

1) `on_checkpoint_save(data, version_key, history)`: this function is responsible for saving the `data` (or a diff of it which you can compute by comparing it with your model `history`, holding every other checkpoint data)
2) `on_checkpoint_restore(version_key, history)`: this function is responsible for restoring data from a previous checkpoint

For example if you want to read from disk pickled objects you might do:

```python
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
```

### Advanced usage

Bulldog has a few nice features for people that use interactive editors (like `ipython` or `jupyter notebook`).

1) You can prevent the same `business_logic` from running multiple times by setting `unique_bl_step=True` in `Model`. This will prevent your state from being modified multiple times if you re-run cells in a notebook.
2) You can restore the version model data at a previous checkpoint by running either `rollback(n_steps)` or `revert_version(Version)`. This is useful both for reproducibility/debugging and for jupyter users who don't want to re-run a whole lengthy analysis after a wrong alteration of the model data.
3) *Testing:* still to be developed. Ideally bulldog will allow you to test every single component in a much easier way and possibly also with mocked data.

