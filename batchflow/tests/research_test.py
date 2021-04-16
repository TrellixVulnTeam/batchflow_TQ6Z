import pytest
from batchflow import Dataset, Pipeline, B, V, F, C
from batchflow.research import *

class TestExperiment:
    def test_callable(self):
        experiment = (Experiment()
            .add_callable('sum', sum, args=[range(10)])
            .save(O('sum'), 'sum')
        )
        executor = Executor(experiment, target='f', meta=None, n_iters=1)
        executor.run()

        assert executor.experiments[0].results['sum'][0] == sum(range(10))

    def test_generator(self):
        def generator(n):
            s = 0
            for i in range(n):
                s += i
                yield s

        experiment = (Experiment()
            .add_generator('sum', generator, n=10)
            .save(O('sum'), 'sum')
        )

        executor = Executor(experiment, target='f', meta=None, n_iters=10)
        executor.run()

        assert executor.experiments[0].results['sum'][9] == sum(range(10))

    def test_configs(self):
        def f(x, y, z):
            return (x, y, z)

        experiment = (Experiment()
            .add_callable('sum', f, x=EC('x'), y=EC('y'), z=EC('z'))
            .save(O('sum'), 'sum')
        )

        executor = Executor(experiment, target='f', meta=None, configs=[{'x': 10}, {'x': 20}],
                            branches_configs=[{'y': 20}, {'y': 30}], executor_config={'z': 5},
                            n_iters=1)
        executor.run()

        assert executor.experiments[0].results['sum'][0] == (10, 20, 5)
        assert executor.experiments[1].results['sum'][0] == (20, 30, 5)

    def test_root(self):
        def root():
            return 10

        experiment = (Experiment()
            .add_callable('root', root, root=True)
            .add_callable('sum', sum, args=[[EC('x'), O('root')]])
            .save(E().outputs['sum'], 'sum')
        )

        executor = Executor(experiment, target='f', meta=None, configs=[{'x': 10}, {'x': 20}], n_iters=1)
        executor.run()

        assert executor.experiments[0].results['sum'][0] == 20
        assert executor.experiments[1].results['sum'][0] == 30

    def test_namespaces(self):
        class MyClass:
            def __init__(self, x):
                self.x = x

            def sum(self):
                return sum(range(self.x))

        experiment = (Experiment()
            .add_namespace('instance', MyClass, x=EC('x'))
            .add_callable('instance.sum')
            .save(O('instance.sum'), 'sum')
        )

        executor = Executor(experiment, target='f', meta=None, configs=[{'x': 10}, {'x': 20}], n_iters=1)
        executor.run()

        assert executor.experiments[0].results['sum'][0] == sum(range(10))
        assert executor.experiments[1].results['sum'][0] == sum(range(20))

    def test_pipeline(self):
        ppl = (Dataset(10).p
            .init_variable('var', 0)
            .update(V('var'), V('var') + B().indices.sum())
            .run_later(1, n_epochs=1, shuffle=False)
        )

        experiment = (Experiment()
            .add_pipeline('ppl', ppl)
            .save(E('ppl').v('var'), save_to='var', iterations_to_execute=['last'])
        )

        executor = Executor(experiment, target='f', meta=None, n_iters=10)
        executor.run()

        assert executor.experiments[0].results['var'][9] == sum(range(10))

    def test_pipeline_with_branches(self):
        root = Dataset(10).p.run_later(1, n_epochs=1, shuffle=False)
        ppl = (Pipeline()
            .init_variable('var', 0)
            .update(V('var'), V('var') + B().indices.sum() * C('x'))
        )

        experiment = (Experiment()
            .add_pipeline('ppl', root, ppl)
            .save(E('ppl_branch').v('var'), save_to='var', iterations_to_execute=['last'])
        )

        executor = Executor(experiment, target='f', meta=None, n_iters=10, configs=[{'x': 10}, {'x': 20}], )
        executor.run()

        assert executor.experiments[0].results['var'][9] == sum(range(10)) * 10
        assert executor.experiments[1].results['var'][9] == sum(range(10)) * 20

    def test_stop_iteration(self):
        def generator(n):
            s = 0
            for i in range(n):
                s += i
                yield s

        def inc(x):
            return x + 1

        experiment = (Experiment()
            .add_generator('sum', generator, n=EC('n'))
            .add_callable('func', inc, x=O('sum'))
            .save(O('sum'), 'sum', iterations_to_execute='last')
            .save(O('func'), 'func', iterations_to_execute='last')
        )

        executor = Executor(experiment, target='f', meta=None, configs=[{'n':10}, {'n': 20}], n_iters=30)
        executor.run()

        assert executor.experiments[0].results['sum'][10] == sum(range(10))
        assert executor.experiments[1].results['sum'][20] == sum(range(20))

        assert executor.experiments[0].results['func'][10] == sum(range(10)) + 1
        assert executor.experiments[1].results['func'][20] == sum(range(20)) + 1

        executor = Executor(experiment, target='f', meta=None, configs=[{'n':10}, {'n': 20}], n_iters=None)
        executor.run()
