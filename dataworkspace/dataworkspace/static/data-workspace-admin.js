var $ = django.jQuery;    
$(function(){
  $('.field-data_type select').on('change', function() {
    var relationSelector = $(this).parents('tr').find('.field-linked_reference_dataset select');
    if ($(this).val() != 8) {
      relationSelector.val(null);
      relationSelector.attr('disabled', 'disabled');
    }
    else {
      relationSelector.removeAttr('disabled');
    }
  });
});
