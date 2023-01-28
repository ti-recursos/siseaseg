odoo.define('product_multi_uom_pos.models',function(require) {
"use strict";

var core = require('web.core');
var models = require('point_of_sale.models');
var OrderlineSuper = models.Orderline;
var field_utils = require('web.field_utils');
var QWeb = core.qweb;
var _t = core._t;
var utils = require('web.utils');
var round_pr = utils.round_precision;
var _super_orderline = models.Orderline.prototype;

models.load_fields('res.partner','activity_id', 'county_id', 'district_id');

models.load_fields('res.country.state', 'code');

models.load_models([{
        model: 'res.country.county',
        fields: ['name','code','state_id'],
        loaded: function(self,county){
            self.county = county;
        },
    },{
        model: 'res.country.district',
        fields: ['name','code','county_id'],
        loaded: function(self,district){
            self.district = district;
        },
    }

],{'before': 'res.country.state'});


models.Orderline = models.Orderline.extend({
    /*Adding uom_id to orderline*/
    initialize: function(attr,options){
        OrderlineSuper.prototype.initialize.call(this, attr, options);

        this.exclude_tax = this ? this.exclude_tax: 0;
    },
    export_as_JSON: function() {
        var result = OrderlineSuper.prototype.export_as_JSON.call(this);
        result.exclude_tax = this.exclude_tax;
        var impuestos = this.get_taxes();
        var new_tax = [];

        if(result.exclude_tax == 1){
            for (var i = 0; i < impuestos.length; i++){
                if(impuestos[i].name != 'Impuesto de Servicio'){
                    new_tax.push(impuestos[i].id);
                }
            }
        }
        else{
            for (var i = 0; i < impuestos.length; i++){
                new_tax.push(impuestos[i].id);
            }
        }
        result.tax_ids = new_tax;
        return result;
    },
    get_all_prices: function(){
        var self = this;

        var price_unit = this.get_unit_price() * (1.0 - (this.get_discount() / 100.0));
        var taxtotal = 0;

        var product =  this.get_product();
        var taxes =  this.pos.taxes;
        var taxes_ids = _.filter(product.taxes_id, t => t in this.pos.taxes_by_id);
        var taxdetail = {};
        var product_taxes = [];

        _(taxes_ids).each(function(el){
            var tax = _.detect(taxes, function(t){
                return t.id === el;
            });
            //console.log(tax);
            if(self.exclude_tax == 1){
                if(tax.name != 'Impuesto de Servicio'){
                    product_taxes.push.apply(product_taxes, self._map_tax_fiscal_position(tax));
                }
            }
            else{
                product_taxes.push.apply(product_taxes, self._map_tax_fiscal_position(tax));
            }
        });
        product_taxes = _.uniq(product_taxes, function(tax) { return tax.id; });


        var all_taxes = this.compute_all(product_taxes, price_unit, this.get_quantity(), this.pos.currency.rounding);
        var all_taxes_before_discount = this.compute_all(product_taxes, this.get_unit_price(), this.get_quantity(), this.pos.currency.rounding);
        _(all_taxes.taxes).each(function(tax) {
            taxtotal += tax.amount;
            taxdetail[tax.id] = tax.amount;
        });

        return {
            "priceWithTax": all_taxes.total_included,
            "priceWithoutTax": all_taxes.total_excluded,
            "priceSumTaxVoid": all_taxes.total_void,
            "priceWithTaxBeforeDiscount": all_taxes_before_discount.total_included,
            "tax": taxtotal,
            "taxDetails": taxdetail,
        };
    },
});

});