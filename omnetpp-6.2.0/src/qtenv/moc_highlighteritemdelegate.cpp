/****************************************************************************
** Meta object code from reading C++ file 'highlighteritemdelegate.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "highlighteritemdelegate.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'highlighteritemdelegate.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate_t {
    uint offsetsAndSizes[8];
    char stringdata0[40];
    char stringdata1[14];
    char stringdata2[1];
    char stringdata3[16];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate_t qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate = {
    {
        QT_MOC_LITERAL(0, 39),  // "omnetpp::qtenv::HighlighterIt..."
        QT_MOC_LITERAL(40, 13),  // "editorCreated"
        QT_MOC_LITERAL(54, 0),  // ""
        QT_MOC_LITERAL(55, 15)   // "editorDestroyed"
    },
    "omnetpp::qtenv::HighlighterItemDelegate",
    "editorCreated",
    "",
    "editorDestroyed"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__HighlighterItemDelegate[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       2,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       2,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    0,   26,    2, 0x106,    1 /* Public | MethodIsConst  */,
       3,    0,   27,    2, 0x106,    2 /* Public | MethodIsConst  */,

 // signals: parameters
    QMetaType::Void,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::HighlighterItemDelegate::staticMetaObject = { {
    QMetaObject::SuperData::link<QStyledItemDelegate::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__HighlighterItemDelegate,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<HighlighterItemDelegate, std::true_type>,
        // method 'editorCreated'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        // method 'editorDestroyed'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::HighlighterItemDelegate::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<HighlighterItemDelegate *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->editorCreated(); break;
        case 1: _t->editorDestroyed(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (HighlighterItemDelegate::*)() const;
            if (_t _q_method = &HighlighterItemDelegate::editorCreated; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (HighlighterItemDelegate::*)() const;
            if (_t _q_method = &HighlighterItemDelegate::editorDestroyed; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
    }
    (void)_a;
}

const QMetaObject *omnetpp::qtenv::HighlighterItemDelegate::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::HighlighterItemDelegate::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__HighlighterItemDelegate.stringdata0))
        return static_cast<void*>(this);
    return QStyledItemDelegate::qt_metacast(_clname);
}

int omnetpp::qtenv::HighlighterItemDelegate::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QStyledItemDelegate::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 2)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 2;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 2)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 2;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::HighlighterItemDelegate::editorCreated()const
{
    QMetaObject::activate(const_cast< omnetpp::qtenv::HighlighterItemDelegate *>(this), &staticMetaObject, 0, nullptr);
}

// SIGNAL 1
void omnetpp::qtenv::HighlighterItemDelegate::editorDestroyed()const
{
    QMetaObject::activate(const_cast< omnetpp::qtenv::HighlighterItemDelegate *>(this), &staticMetaObject, 1, nullptr);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
