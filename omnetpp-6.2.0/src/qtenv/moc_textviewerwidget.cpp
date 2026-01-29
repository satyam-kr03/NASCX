/****************************************************************************
** Meta object code from reading C++ file 'textviewerwidget.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "textviewerwidget.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'textviewerwidget.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget_t {
    uint offsetsAndSizes[50];
    char stringdata0[33];
    char stringdata1[11];
    char stringdata2[1];
    char stringdata3[10];
    char stringdata4[7];
    char stringdata5[13];
    char stringdata6[10];
    char stringdata7[18];
    char stringdata8[18];
    char stringdata9[23];
    char stringdata10[13];
    char stringdata11[8];
    char stringdata12[8];
    char stringdata13[14];
    char stringdata14[25];
    char stringdata15[17];
    char stringdata16[17];
    char stringdata17[18];
    char stringdata18[20];
    char stringdata19[21];
    char stringdata20[6];
    char stringdata21[19];
    char stringdata22[12];
    char stringdata23[9];
    char stringdata24[8];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget_t qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget = {
    {
        QT_MOC_LITERAL(0, 32),  // "omnetpp::qtenv::TextViewerWidget"
        QT_MOC_LITERAL(33, 10),  // "caretMoved"
        QT_MOC_LITERAL(44, 0),  // ""
        QT_MOC_LITERAL(45, 9),  // "lineIndex"
        QT_MOC_LITERAL(55, 6),  // "column"
        QT_MOC_LITERAL(62, 12),  // "rightClicked"
        QT_MOC_LITERAL(75, 9),  // "globalPos"
        QT_MOC_LITERAL(85, 17),  // "onAutoScrollTimer"
        QT_MOC_LITERAL(103, 17),  // "onCaretBlinkTimer"
        QT_MOC_LITERAL(121, 22),  // "onHeaderSectionResized"
        QT_MOC_LITERAL(144, 12),  // "logicalIndex"
        QT_MOC_LITERAL(157, 7),  // "oldSize"
        QT_MOC_LITERAL(165, 7),  // "newSize"
        QT_MOC_LITERAL(173, 13),  // "copySelection"
        QT_MOC_LITERAL(187, 24),  // "copySelectionUnformatted"
        QT_MOC_LITERAL(212, 16),  // "onContentChanged"
        QT_MOC_LITERAL(229, 16),  // "onLinesDiscarded"
        QT_MOC_LITERAL(246, 17),  // "numLinesDiscarded"
        QT_MOC_LITERAL(264, 19),  // "onStatusTextChanged"
        QT_MOC_LITERAL(284, 20),  // "scrolledHorizontally"
        QT_MOC_LITERAL(305, 5),  // "value"
        QT_MOC_LITERAL(311, 18),  // "scrolledVertically"
        QT_MOC_LITERAL(330, 11),  // "revealCaret"
        QT_MOC_LITERAL(342, 8),  // "QMargins"
        QT_MOC_LITERAL(351, 7)   // "margins"
    },
    "omnetpp::qtenv::TextViewerWidget",
    "caretMoved",
    "",
    "lineIndex",
    "column",
    "rightClicked",
    "globalPos",
    "onAutoScrollTimer",
    "onCaretBlinkTimer",
    "onHeaderSectionResized",
    "logicalIndex",
    "oldSize",
    "newSize",
    "copySelection",
    "copySelectionUnformatted",
    "onContentChanged",
    "onLinesDiscarded",
    "numLinesDiscarded",
    "onStatusTextChanged",
    "scrolledHorizontally",
    "value",
    "scrolledVertically",
    "revealCaret",
    "QMargins",
    "margins"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__TextViewerWidget[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
      14,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       2,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    2,   98,    2, 0x06,    1 /* Public */,
       5,    3,  103,    2, 0x06,    4 /* Public */,

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       7,    0,  110,    2, 0x09,    8 /* Protected */,
       8,    0,  111,    2, 0x09,    9 /* Protected */,
       9,    3,  112,    2, 0x09,   10 /* Protected */,
      13,    0,  119,    2, 0x09,   14 /* Protected */,
      14,    0,  120,    2, 0x09,   15 /* Protected */,
      15,    0,  121,    2, 0x0a,   16 /* Public */,
      16,    1,  122,    2, 0x0a,   17 /* Public */,
      18,    0,  125,    2, 0x0a,   19 /* Public */,
      19,    1,  126,    2, 0x0a,   20 /* Public */,
      21,    1,  129,    2, 0x0a,   22 /* Public */,
      22,    1,  132,    2, 0x0a,   24 /* Public */,
      22,    0,  135,    2, 0x2a,   26 /* Public | MethodCloned */,

 // signals: parameters
    QMetaType::Void, QMetaType::Int, QMetaType::Int,    3,    4,
    QMetaType::Void, QMetaType::QPoint, QMetaType::Int, QMetaType::Int,    6,    3,    4,

 // slots: parameters
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int, QMetaType::Int, QMetaType::Int,   10,   11,   12,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   17,
    QMetaType::Void,
    QMetaType::Void, QMetaType::Int,   20,
    QMetaType::Void, QMetaType::Int,   20,
    QMetaType::Void, 0x80000000 | 23,   24,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::TextViewerWidget::staticMetaObject = { {
    QMetaObject::SuperData::link<QAbstractScrollArea::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__TextViewerWidget,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<TextViewerWidget, std::true_type>,
        // method 'caretMoved'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'rightClicked'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QPoint, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'onAutoScrollTimer'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onCaretBlinkTimer'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onHeaderSectionResized'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'copySelection'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'copySelectionUnformatted'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onContentChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'onLinesDiscarded'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'onStatusTextChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'scrolledHorizontally'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'scrolledVertically'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<int, std::false_type>,
        // method 'revealCaret'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<const QMargins &, std::false_type>,
        // method 'revealCaret'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::TextViewerWidget::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<TextViewerWidget *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->caretMoved((*reinterpret_cast< std::add_pointer_t<int>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<int>>(_a[2]))); break;
        case 1: _t->rightClicked((*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<int>>(_a[2])),(*reinterpret_cast< std::add_pointer_t<int>>(_a[3]))); break;
        case 2: _t->onAutoScrollTimer(); break;
        case 3: _t->onCaretBlinkTimer(); break;
        case 4: _t->onHeaderSectionResized((*reinterpret_cast< std::add_pointer_t<int>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<int>>(_a[2])),(*reinterpret_cast< std::add_pointer_t<int>>(_a[3]))); break;
        case 5: _t->copySelection(); break;
        case 6: _t->copySelectionUnformatted(); break;
        case 7: _t->onContentChanged(); break;
        case 8: _t->onLinesDiscarded((*reinterpret_cast< std::add_pointer_t<int>>(_a[1]))); break;
        case 9: _t->onStatusTextChanged(); break;
        case 10: _t->scrolledHorizontally((*reinterpret_cast< std::add_pointer_t<int>>(_a[1]))); break;
        case 11: _t->scrolledVertically((*reinterpret_cast< std::add_pointer_t<int>>(_a[1]))); break;
        case 12: _t->revealCaret((*reinterpret_cast< std::add_pointer_t<QMargins>>(_a[1]))); break;
        case 13: _t->revealCaret(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (TextViewerWidget::*)(int , int );
            if (_t _q_method = &TextViewerWidget::caretMoved; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (TextViewerWidget::*)(QPoint , int , int );
            if (_t _q_method = &TextViewerWidget::rightClicked; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::TextViewerWidget::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::TextViewerWidget::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__TextViewerWidget.stringdata0))
        return static_cast<void*>(this);
    return QAbstractScrollArea::qt_metacast(_clname);
}

int omnetpp::qtenv::TextViewerWidget::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QAbstractScrollArea::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 14)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 14;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 14)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 14;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::TextViewerWidget::caretMoved(int _t1, int _t2)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void omnetpp::qtenv::TextViewerWidget::rightClicked(QPoint _t1, int _t2, int _t3)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t3))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
