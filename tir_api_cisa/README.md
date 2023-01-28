**API que permite a SHCISA conectarse con odoo como intermediario con los bancos, para procesar diferentes metodos de pago**
Pagos bancarios, BNPAR, Pago automatico.

    Estos son los códigos de error enviados por el banco
    '''
    '00': 'Transaccion exitosa',
    '01': 'Cedula o Contrato no Existe',
    '02': 'Pagar en la Oficina',
    '03': 'No existe pago para esta reversion',
    '04': 'No se puede cancelar, hay pagos más antiguos',
    '05': 'Total recaudado por pagos no coincide',
    '06': 'Monto de comision no coincide',  # No se implementó
    '07': 'No existe pagos pendientes',
    '08': 'Ya esta afiliado',  # No se implementó
    '09': 'Ya esta desafiliado',  # No se implementó
    '''
    Estos son los códigos definidos por TI Recursos S.A.
    '''
    '10': 'No se encontro el parametro r',
    '11': 'No se encontraron todos los parametros esperados',
    '12': 'La fecha del pago y de la reversion son distintas',
    '13': 'Valor del parametro tipo inesperado',
    '14': 'No se encontro un banco que coincida con la informacion brindada',
    '15': 'Metodo inesperado',
