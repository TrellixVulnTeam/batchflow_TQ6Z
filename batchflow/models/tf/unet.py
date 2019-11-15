"""
Ronneberger O. et al "`U-Net: Convolutional Networks for Biomedical Image Segmentation
<https://arxiv.org/abs/1505.04597>`_"

Zhou Z. et al "UNet++: A Nested U-Net Architecture for Medical Image Segmentation
<https://arxiv.org/abs/1807.10165>`_"
"""
from .encoder_decoder import EncoderDecoder
from .layers import conv_block, combine
from ..utils import unpack_args

class UNet(EncoderDecoder):
    """ UNet-like model

    **Configuration**

    inputs : dict
        dict with 'images' and 'masks' (see :meth:`~.TFModel._make_inputs`)

    body : dict
        encoder : dict
            num_stages : int
                number of downsampling blocks (default=4)
            blocks : dict
                Parameters for pre-processing blocks:

                filters : None, int, list of ints or list of lists of ints
                    The number of filters in the output tensor.
                    If int, same number of filters applies to all layers on all stages
                    If list of ints, specifies number of filters in each layer of different stages
                    If list of list of ints, specifies number of filters in different layers on different stages
                    If not given or None, filters parameters in encoder/blocks, decoder/blocks and decoder/upsample
                    default to values which make number of filters double
                    on each stage of encoding and halve on each stage of decoding,
                    provided that `decoder/skip` is `True`. Specify `filters=None` explicitly
                    if you want to use custom `num_steps` and infer `filters`

        decoder : dict
            num_stages : int
                number of upsampling blocks. Defaults to the number of downsamplings.

            factor : None, int or list of ints
                If int, the total upsampling factor for all stages combined.
                If list, upsampling factors for each stage
                If not given or None, defaults to [2]*num_stages

            blocks : dict
                Parameters for post-processing blocks:

                filters : None, int, list of ints or list of lists of ints
                    same as encoder/blocks/filters

            upsample : dict
                Parameters for upsampling (see :func:`~.layers.upsample`).

                filters : int, list of ints or list of lists of ints
                    same as encoder/blocks/filters

    for more parameters see (see :class:`~.EncoderDecoder`)
    """
    @classmethod
    def default_config(cls):
        config = super().default_config()

        config['body/encoder/num_stages'] = 4
        config['body/encoder/order'] = ['block', 'skip', 'downsampling']
        config['body/encoder/blocks'] += dict(layout='cna cna', kernel_size=3, filters=[64, 128, 256, 512])
        config['body/embedding'] += dict(layout='cna cna', kernel_size=3)
        config['body/decoder/order'] = ['upsampling', 'combine', 'block']
        config['body/decoder/blocks'] += dict(layout='cna cna', kernel_size=3, filters=[512, 256, 128, 64])

        config['loss'] = 'ce'
        return config

    def build_config(self, names=None):
        config = super().build_config(names)

        num_stages = config.get('body/encoder/num_stages')

        if config.get('body/encoder/blocks/filters') is None:
            config['body/encoder/blocks/filters'] = [64 * 2**i for i in range(num_stages)]

        if config.get('body/embedding/filters') is None:
            config['body/embedding/filters'] = 64 * 2**num_stages

        if config.get('body/decoder/blocks/filters') is None:
            enc_filters = config.get('body/encoder/blocks/filters')
            config['body/decoder/blocks/filters'] = enc_filters[::-1]

        if config.get('body/decoder/upsample/filters') is None:
            config['body/decoder/upsample/filters'] = config.get('body/decoder/blocks/filters')

        return config

class UNetPP(UNet):
    """ UNet-like model with dense connections of convilutional layers

    **Configuration**

    inputs : dict
        dict with 'images' and 'masks' (see :meth:`~.TFModel._make_inputs`)

    body : dict
        encoder : dict
            num_stages : int
                number of downsampling blocks (default=4)
            blocks : dict
                Parameters for pre-processing blocks:

                filters : None, int, list of ints or list of lists of ints
                    The number of filters in the output tensor.
                    If int, same number of filters applies to all layers on all stages
                    If list of ints, specifies number of filters in each layer of different stages
                    If list of list of ints, specifies number of filters in different layers on different stages
                    If not given or None, filters parameters in encoder/blocks, decoder/blocks and decoder/upsample
                    default to values which make number of filters double
                    on each stage of encoding and halve on each stage of decoding,
                    provided that `decoder/skip` is `True`. Specify `filters=None` explicitly
                    if you want to use custom `num_steps` and infer `filters`

        decoder : dict
            num_stages : int
                number of upsampling blocks. Defaults to the number of downsamplings.

            factor : None, int or list of ints
                If int, the total upsampling factor for all stages combined.
                If list, upsampling factors for each stage
                If not given or None, defaults to [2]*num_stages

            blocks : dict
                Parameters for post-processing blocks:

                filters : None, int, list of ints or list of lists of ints
                    same as encoder/blocks/filters

            upsample : dict
                Parameters for upsampling (see :func:`~.layers.upsample`).

                filters : int, list of ints or list of lists of ints
                    same as encoder/blocks/filters

            dense : dict
                Parameters for dense block on skip connections including parameters for conv_block

                upsample : dict
                    upsample parameters for block

    for more parameters see (see :class:`~.EncoderDecoder`)
    """
    def build_config(self, names=None):
        config = super().build_config(names)

        num_stages = config.get('body/encoder/num_stages')

        if config.get('body/decoder/dense/upsample') is None:
            config['body/decoder/dense/upsample'] = dict(layout='tna')

        if config.get('body/decoder/dense/filters') is None:
            config['body/decoder/dense/filters'] = [32 * 2**i for i in range(num_stages)]

        if config.get('body/decoder/dense/layout') is None:
            config['body/decoder/dense/layout'] = 'cna'

        if config.get('body/decoder/dense/kernel') is None:
            config['body/decoder/dense/kernel'] = 3

        if config.get('body/decoder/dense/combine_op') is None:
            config['body/decoder/dense/combine_op'] = 'concat'

        return config

    @classmethod
    def decoder(cls, inputs, name='decoder', **kwargs):
        decoder_filters = kwargs['upsample']['filters']

        num_stages = kwargs.pop('num_stages') or len(inputs)-2

        combine_op = kwargs['dense']['combine_op']
        combine_args = {'op': combine_op if isinstance(combine_op, str) else '',
                        'data_format': kwargs.get('data_format'),
                        **(combine_op if isinstance(combine_op, dict) else {})}

        for i in range(1, num_stages):
            _inputs = inputs[:i] + [inputs[i]] * 2

            _kwargs = kwargs
            _kwargs['upsample'] = _kwargs['dense']['upsample']
            _kwargs['upsample']['filters'] = decoder_filters[-i:]
            _kwargs['blocks']['filters'] = decoder_filters[-i:]

            outputs = super().decoder(_inputs, name=name,
                                      return_all=True, **{**_kwargs, 'num_stages': i})

            for j, x in enumerate(inputs[:i]):
                x = combine([x, outputs[::-1][j]], **combine_args)

                dense_args = {**unpack_args(kwargs['dense'], j, num_stages), **kwargs}
                x = conv_block(x, name='x-{}-{}'.format(j, i), **dense_args)

                inputs[j] = combine([x, inputs[j]], name='concat-{}-{}'.format(j, i-j), **combine_args)

        kwargs['upsample']['filters'] = decoder_filters
        kwargs['blocks']['filters'] = decoder_filters
        print(inputs)
        return super().decoder(inputs, name=name, filters=decoder_filters,
                               return_all=False, **{**kwargs, 'num_stages': num_stages})
