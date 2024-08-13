import tinymce from 'tinymce';

/* Default icons are required. After that, import custom icons if applicable */
import 'tinymce/icons/default/icons.min.js';

/* Required TinyMCE components */
import 'tinymce/themes/silver/theme.min.js';
import 'tinymce/models/dom/model.min.js';

/* Import a skin (can be a custom skin instead of the default) */
import 'tinymce/skins/ui/oxide/skin.js';

import 'tinymce/plugins/link';
import 'tinymce/plugins/advlist';
import 'tinymce/plugins/code';
import 'tinymce/plugins/codesample';
import 'tinymce/plugins/media';
import 'tinymce/plugins/table';
import 'tinymce/plugins/wordcount';
import 'tinymce/plugins/insertdatetime';
import 'tinymce/plugins/autolink';
import 'tinymce/plugins/lists';
import 'tinymce/plugins/visualblocks';
import 'tinymce/plugins/searchreplace';
import 'tinymce/icons/default/icons';
import 'tinymce/plugins/fullscreen';

import contentUiSkinCss from 'tinymce/skins/ui/oxide/content.js';
import contentCss from 'tinymce/skins/content/default/content.js';

const tinymce_default_config = {
  skin_url: 'default',
  content_css: 'default',
  // content_css: false,
  content_style: contentUiSkinCss.toString() + '\n' + contentCss.toString(),
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

const tinymce_link_config = {
  ...tinymce_default_config,
  plugins: ['link'],
  toolbar: 'link'
};

const initTinymce = (selector, config = tinymce_default_config) => {
  tinymce.init({
    selector,
    ...config
  });
};

initTinymce('textarea[data-type="rich-text-editor"]');
initTinymce(
  'textarea[data-type="rich-text-editor-link-only"]',
  tinymce_link_config
);
