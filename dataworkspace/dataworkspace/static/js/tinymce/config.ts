import type { RawEditorOptions } from 'tinymce';
import tinymce from 'tinymce';

type TinyMceOptions = Partial<RawEditorOptions>;

const tinymce_default_config: TinyMceOptions = {
  height: '320px',
  width: '900px',
  menubar: false,
  custom_undo_redo_levels: 10,
  license_key: 'gpl',
  plugins:
    'advlist autolink lists link searchreplace visualblocks code codesample fullscreen insertdatetime media table code wordcount',
  toolbar:
    'undo redo | blocks | bold italic | fontselect fontsizeselect formatselect | alignleft aligncenter alignright alignjustify | numlist bullist checklist | link codesample code'
};

const tinymce_link_config: TinyMceOptions = {
  ...tinymce_default_config,
  plugins: ['link'],
  toolbar: 'link'
};

const initTinymce = (
  selector: string,
  config: TinyMceOptions = tinymce_default_config
) => {
  tinymce.init({
    selector: `textarea${selector}`,
    ...config
  });
};

initTinymce('#id_description');
initTinymce('#id_notes');
initTinymce('#id_restrictions_on_usage', tinymce_link_config);
