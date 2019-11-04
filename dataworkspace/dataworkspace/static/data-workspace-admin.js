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

    $('.field-name input').on('keyup', function(){
	let name = $(this).attr('name');
	let index = name.match(/(?!=fields-)[0-9]+(?=-name)/)
	let columnField = $(`.field-column_name input[name="fields-${index}-column_name"]`);
	if(!columnField[0].hasAttribute('_change')){
	    columnField.attr('_change', 0)
	}

	if(parseInt(columnField.attr('_change')) == 0){
	    let columnName;
	    let urlified = URLify($(this).val());
	    if(urlified == ''){
		columnName = ''
	    } else {
		columnName = urlified.split('-').join('_');
	    }
	    columnField.val(columnName)
	}
    });

    $('.field-column_name input').on('keyup', function(){
	$(this).attr('_change', 1);
    });
});

