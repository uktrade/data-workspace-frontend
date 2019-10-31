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

console.log('test');

$(function(){
    let _changed = false;
    let nameInput = $('#referencedataset_form input[name="name"]');
    let tableNameInput = $('#referencedataset_form input[name="table_name"]');
    nameInput.on('keyup', function(){
	if(_changed == false){
	    let tableName;
	    let urlified = URLify($(this).val());
	    if(urlified == ''){
		tableName = '';
	    } else {
		tableName = `ref_${urlified.split('-').join('_')}`;
	    }
	    tableNameInput.val(tableName);
	}
    });
    tableNameInput.on('keyup', function(){
	_changed = true;
    });
});
