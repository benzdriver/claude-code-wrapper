#!/bin/bash

# Claude Code Wrapper - 清理旧文档脚本

echo "🧹 清理旧的测试文档..."
echo "=================================================="

# 创建一个归档目录
ARCHIVE_DIR="docs/archive/test_coverage_project"
mkdir -p $ARCHIVE_DIR

echo "📁 创建归档目录: $ARCHIVE_DIR"

# 需要保留的重要文档
KEEP_DOCS=(
    "ENHANCED_MODULES_TEST_SUMMARY.md"
    "TEST_COVERAGE_FINAL_REPORT.md"
    "TESTING_GUIDE.md"
    "TEST_VALIDATION_REPORT.md"
    "PROJECT_COMPLETION_SUMMARY.md"
)

# 需要归档的旧文档
OLD_DOCS=(
    "API_TEST_COVERAGE_SUMMARY.md"
    "COMMAND_MANAGER_TEST_SUMMARY.md"
    "COMPREHENSIVE_TEST_COVERAGE_REPORT.md"
    "FINAL_TEST_COVERAGE_SUMMARY.md"
    "FINAL_TESTING_SUMMARY.md"
    "MODULE_TEST_COVERAGE_MAP.md"
    "TEST_CLEANUP_COMPLETE.md"
    "TEST_CLEANUP_PLAN.md"
    "TEST_CLEANUP_SUMMARY.md"
    "TEST_COVERAGE_ANALYSIS.md"
    "TEST_COVERAGE_REPORT.md"
    "TEST_DOCUMENTATION_SUMMARY.md"
    "TEST_FILES_TO_DELETE.md"
    "TEST_REFACTORING_PLAN.md"
    "TEST_RUN_RESULTS.md"
    "TEST_STRUCTURE_SUMMARY.md"
    "TESTING_STATUS_REALITY.md"
    "COVERAGE_*.md"
    "ACTUAL_COVERAGE_REPORT.md"
)

echo ""
echo "📋 归档旧文档..."
echo "--------------------------------------------------"

# 移动旧文档到归档目录
for doc in "${OLD_DOCS[@]}"; do
    if ls $doc 1> /dev/null 2>&1; then
        mv $doc $ARCHIVE_DIR/ 2>/dev/null && echo "  ✅ 归档: $doc"
    fi
done

echo ""
echo "📌 保留的重要文档:"
echo "--------------------------------------------------"
for doc in "${KEEP_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "  ✅ $doc"
    fi
done

# 创建一个 README 在归档目录
cat > $ARCHIVE_DIR/README.md << EOF
# 测试覆盖率提升项目归档

这个目录包含了测试覆盖率提升项目过程中生成的所有文档。

## 重要文档已移至项目根目录：
- ENHANCED_MODULES_TEST_SUMMARY.md - 详细实施记录
- TEST_COVERAGE_FINAL_REPORT.md - 最终项目报告
- TESTING_GUIDE.md - 测试指南
- TEST_VALIDATION_REPORT.md - 测试验证报告
- PROJECT_COMPLETION_SUMMARY.md - 项目完成总结

## 归档日期
$(date +"%Y-%m-%d %H:%M:%S")
EOF

echo ""
echo "📄 创建归档 README"

# 清理临时文件
echo ""
echo "🗑️  清理临时文件..."
echo "--------------------------------------------------"
find . -name "*.pyc" -delete 2>/dev/null && echo "  ✅ 清理 .pyc 文件"
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null && echo "  ✅ 清理 __pycache__ 目录"
rm -f .coverage 2>/dev/null && echo "  ✅ 清理 .coverage 文件"

echo ""
echo "📊 清理结果统计:"
echo "--------------------------------------------------"
echo "  归档文档数: $(ls -1 $ARCHIVE_DIR/*.md 2>/dev/null | wc -l)"
echo "  保留文档数: ${#KEEP_DOCS[@]}"

echo ""
echo "✅ 清理完成！"
echo ""
echo "建议的 .gitignore 更新:"
echo "--------------------------------------------------"
cat << EOF
# Test coverage archives
docs/archive/

# Python
__pycache__/
*.pyc
.coverage
htmlcov/

# Environment
.env
.env.test
EOF

echo ""