odoo.define('product_multi_uom_pos.multi_uom_widget',function(require) {
    "use strict";

var gui = require('point_of_sale.Gui');
var core = require('web.core');
var QWeb = core.qweb;

    const NumberBuffer = require('point_of_sale.NumberBuffer');
    const { onChangeOrder, useBarcodeReader } = require('point_of_sale.custom_hooks');
    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const { useListener } = require('web.custom_hooks');
    const { useState, useRef } = owl.hooks;




    class MultiUomWidget extends PosComponent {


        constructor() {
            super(...arguments);

            this.options = {};
            this.uom_list = [];

            }

        mounted(options){

            this.render();

        }


    click_confirm(){
        var self = this;
        var order = this.env.pos.get_order();
        var orderline = order.get_selected_orderline();


        var impuestos = orderline.get_taxes();

        var new_tax = [];
        var bk_tax = [];

        orderline.exclude_tax = 1;

            for (var i = 0; i < impuestos.length; i++){
                if(impuestos[i].name != 'Impuesto de Servicio'){
                    new_tax.push(impuestos[i].id);
                }
                bk_tax.push(impuestos[i].id);
            }

        orderline.product.taxes_id = new_tax;

        /*Updating the orderlines*/
        order.remove_orderline(orderline);
        order.add_orderline(orderline);

        orderline.product.taxes_id = bk_tax;

        this.trigger('close-popup');
        return;

    }
    click_cancel(){
        this.trigger('close-popup');
    }

    }


    MultiUomWidget.template = 'MultiUomWidget';
    MultiUomWidget.defaultProps = {
        confirmText: 'Return',
        cancelText: 'Cancel',
        title: 'Confirm ?',
        body: '',
    };
    Registries.Component.add(MultiUomWidget);
    return MultiUomWidget;
});

