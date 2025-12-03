/**
 * Dynamic Course → Module Filtering for LiveClass, Assignment, Quiz Admin
 * 
 * This script provides real-time filtering of module dropdowns based on
 * the selected course, without requiring a page reload.
 */

(function($) {
    'use strict';
    
    $(document).ready(function() {
        // Find course and module fields
        var $courseField = $('#id_course');
        var $moduleField = $('#id_module');

        if ($courseField.length === 0 || $moduleField.length === 0) {
            return; // Fields not found, exit
        }

        function showNoModulesMessage() {
            if ($moduleField.find('option').length === 1) {
                if ($moduleField.siblings('.course-module-help').length === 0) {
                    $moduleField.after(
                        '<p class="course-module-help help" style="color: #d32f2f; margin-top: 5px;">' +
                        '⚠️ No modules found for this course. Please create modules first.' +
                        '</p>'
                    );
                }
            } else {
                $moduleField.siblings('.course-module-help').remove();
            }
        }

        // Fetch modules for a course slug via API and populate module select
        function loadModulesForCourse(courseSlug) {
            // Clear current options (keep first empty option)
            $moduleField.find('option:not(:first)').remove();

            if (!courseSlug) {
                showNoModulesMessage();
                return;
            }

            var url = '/api/courses/' + encodeURIComponent(courseSlug) + '/modules/';
            $.get(url, function(response) {
                // response expected in api_response format: { success: true, message: '', data: [...] }
                var modules = (response && response.data) ? response.data : [];
                modules.forEach(function(m) {
                    $moduleField.append(
                        $('<option></option>').val(m.id).text((m.order ? (m.order + '. ') : '') + m.title)
                    );
                });

                showNoModulesMessage();
            }).fail(function() {
                // On error, leave module options as-is and show message
                showNoModulesMessage();
            });
        }

        // Bind change event
        $courseField.on('change', function() {
            var slug = $(this).val();
            loadModulesForCourse(slug);
        });

        // Add visual feedback
        $courseField.parent().find('label').append(
            ' <span style="color: #1976d2; font-weight: bold;">→ Step 1</span>'
        );
        $moduleField.parent().find('label').append(
            ' <span style="color: #1976d2; font-weight: bold;">→ Step 2</span>'
        );

        // If a course is pre-selected on load, trigger load
        var initialCourse = $courseField.val();
        if (initialCourse) {
            loadModulesForCourse(initialCourse);
        }
    });
})(django.jQuery);
